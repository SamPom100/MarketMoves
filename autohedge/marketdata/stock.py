from yfinance.ticker import Ticker
from matplotlib import pyplot as plt
from scipy.ndimage import gaussian_filter1d
import pandas as pd

class FilteredOptionChain:
    def __init__(self, option_chain):
        option_chain.calls["midprice"] = (option_chain.calls["bid"] + option_chain.calls["ask"]) / 2
        option_chain.puts["midprice"] = (option_chain.puts["bid"] + option_chain.puts["ask"]) / 2
        self.calls = option_chain.calls[option_chain.calls["openInterest"] > 0]
        self.calls = option_chain.calls[option_chain.calls["volume"] > 0]
        self.puts = option_chain.puts[option_chain.puts["openInterest"] > 0]
        self.calls = self.calls[self.calls["midprice"] > 0]
        self.puts = self.puts[self.puts["midprice"] > 0]
        self.puts = option_chain.puts[option_chain.puts["volume"] > 0]

class Stock(Ticker):
    def __init__(self, symbol: str):
        super().__init__(symbol)
        self.option_chain_cache = {}
        self.symbol = symbol

    '''
    CLASS METHODS
    '''

    def get_option_dates(self):
        return super().options

    def get_calls(self, date: str):
        return self.__get_option_chain(date).calls

    def get_puts(self, date: str):
        return self.__get_option_chain(date).puts
        
    def get_current_price(self):
        return super().info["regularMarketPrice"]
    
    def get_expected_moves_straddle(self):
        return {date: self.__get_expected_move_straddle(date) for date in self.get_option_dates()}
    
    def get_expected_moves_strangle(self):
        return {date: self.__get_expected_move_strangle(date) for date in self.get_option_dates()}
    
    def get_expected_moves_all(self):
        straddle = self.get_expected_moves_straddle()
        strangle = self.get_expected_moves_strangle()
        return {date: round((straddle[date] + strangle[date]) / 2, 2) for date in strangle}

    def calculate_butterfly_probabilities(self, date: str):
        return self.__calculate_butterfly_probabilities_helper(date)

    def plot_butterfly_probabilities(self, date: str):
        self.__plot_butterfly_probabilities_helper(date)

    '''
    HELPER METHODS
    '''

    def __get_option_chain(self, date: str):
        if date in self.option_chain_cache:
            return self.option_chain_cache[date]
        else:
            option_chain = super().option_chain(date)
            self.option_chain_cache[date] = FilteredOptionChain(option_chain)
            return self.option_chain_cache[date]

    def __get_atm_straddle(self, date: str):
        calls = self.get_calls(date)
        puts = self.get_puts(date)
        price = self.get_current_price()
        
        closest_call = calls[calls["strike"] >= price].iloc[0]
        closest_put = puts[puts["strike"] <= price].iloc[-1]
        
        return (closest_call["midprice"], closest_put["midprice"])

    def __get_otm_strangle(self, date: str):
        calls = self.get_calls(date)
        puts = self.get_puts(date)
        price = self.get_current_price()
        
        otm_call = calls[calls["strike"] > price].iloc[0]
        otm_put = puts[puts["strike"] < price].iloc[-1]
        
        return (otm_call["midprice"], otm_put["midprice"])

    def __get_expected_move_straddle(self, date: str):
        call_price, put_price = self.__get_atm_straddle(date)
        price = self.get_current_price()
        
        return round(100 * ((call_price + put_price) * 0.85) / price, 2)

    def __get_expected_move_strangle(self, date: str):        
        straddle_call, straddle_put = self.__get_atm_straddle(date)
        strangle_call, strangle_put = self.__get_otm_strangle(date)
        
        straddle_value = straddle_call + straddle_put
        strangle_value = strangle_call + strangle_put
        
        price = self.get_current_price()
        
        return round(100 * ((straddle_value + strangle_value) / 2) / price, 2)

    def __get_butterflies_helper(self, option_chain):
        results = {}
        
        for i in range(1, len(option_chain) - 1, 1):
            bottom_call = option_chain.iloc[i - 1]
            middle_call = option_chain.iloc[i]
            top_call = option_chain.iloc[i + 1]

            #ensure strike prices are equidistant
            if not middle_call["strike"] - bottom_call["strike"] == top_call["strike"] - middle_call["strike"]:
                continue

            butterfly_price = (bottom_call["midprice"] - (2 * middle_call["midprice"])) + top_call["midprice"]
            butterfly_maxprofit = middle_call["strike"] - bottom_call["strike"] 
            butterfly_prob = butterfly_price / butterfly_maxprofit
            if butterfly_prob > 0.5 or butterfly_prob < -0.5:
                continue
            
            results[float(middle_call["strike"])] = round(float(butterfly_prob * 100), 3)
        return pd.DataFrame(results.items(), columns=['strike', 'probability'])

    def __calculate_butterfly_probabilities_helper(self, date: str):
        calls = self.__get_butterflies_helper(self.get_calls(date))
        puts = self.__get_butterflies_helper(self.get_puts(date))
        results = pd.merge(calls, puts, on='strike', how='outer')

        def helper(row):
            if pd.isna(row['probability_x']):
                return row['probability_y']
            elif pd.isna(row['probability_y']):
                return row['probability_x']
            else:
                return (row['probability_x'] + row['probability_y']) / 2
        results['probability'] = results.apply(helper, axis=1)
        results = results[['strike', 'probability']]
        results['probability'] = results['probability'].abs()
        return results
    
    def __normalize_data_gaussian(self, results):
        results['probability'] = gaussian_filter1d(results['probability'], sigma=4)
        return results
    
    def __normalize_data_idr(self, results):
        Q1 = results['probability'].quantile(0.25)
        Q3 = results['probability'].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        results = results[(results['probability'] >= lower_bound) & (results['probability'] <= upper_bound)]
        return results
    
    def __normalize_data_combined(self, results):
        results = self.__normalize_data_idr(results)
        results = self.__normalize_data_gaussian(results)
        return results

    def __plot_butterfly_probabilities_helper(self, date: str):
        results = self.__calculate_butterfly_probabilities_helper(date)

        # TODO - find a better smoothing method
        results = self.__normalize_data_combined(results)

        plt.figure(figsize=(12, 6))
        plt.scatter(results['strike'], results['probability'], s=50, alpha=0.7)

        current_price = self.get_current_price()
        plt.axvline(x=current_price, color='green', linestyle='--', alpha=0.5, 
                    label=f'Current Price: ${current_price:.2f}')

        plt.xlabel('Strike Price ($)')
        plt.ylabel('Probability (%)')
        plt.title(f'Butterfly-Implied Probability Distribution for {self.symbol} - {date}')
        plt.plot(results['strike'], results['probability'], 'k--', alpha=0.3)
        plt.axhline(y=0, color='r', linestyle='-', alpha=0.3)
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.show()

        return results
