from yfinance.ticker import Ticker

class Stock(Ticker):
    def __init__(self, symbol: str):
        super().__init__(symbol)
        self.option_chain_cache = {}

    def get_option_dates(self):
        return super().options

    def get_calls(self, date: str):
        if date in self.option_chain_cache:
            return self.option_chain_cache[date].calls
        else:
            self.option_chain_cache[date] = super().option_chain(date)
            return self.option_chain_cache[date].calls

    def get_puts(self, date: str):
        if date in self.option_chain_cache:
            return self.option_chain_cache[date].puts
        else:
            self.option_chain_cache[date] = super().option_chain(date)
            return self.option_chain_cache[date].puts
        
    def get_current_price(self):
        return super().info['regularMarketPrice']
    
    def get_expected_moves_straddle(self):
        return {date: self.__get_expected_move_straddle(date) for date in self.get_option_dates()}
    
    def get_expected_moves_strangle(self):
        return {date: self.__get_expected_move_strangle(date) for date in self.get_option_dates()}
    
    def get_expected_moves_all(self):
        straddle = self.get_expected_moves_straddle()
        strangle = self.get_expected_moves_strangle()
        return {date: round((straddle[date] + strangle[date]) / 2, 2) for date in strangle}
    
    def get_butterfly_all(self, date: str):
        calls = self.get_calls(date)
        strikes = calls["strike"].tolist()
        butterflies = {}
        for i in range(1, len(strikes) - 1, 1):
            try:
                butterflies[strikes[i]] = self.__get_butterfly(date, strikes[i - 1], strikes[i], strikes[i + 1])
            except ValueError:
                butterflies[strikes[i]] = None
        return butterflies
    
    def __get_midprice(self, option_chain):
        return round(float((option_chain["ask"] + option_chain["bid"]) / 2), 2)

    def __get_atm_straddle(self, date: str):
        calls = self.get_calls(date)
        puts = self.get_puts(date)
        price = self.get_current_price()
        
        closest_call = calls[calls["strike"] >= price].iloc[0]
        closest_put = puts[puts["strike"] <= price].iloc[-1]
        
        return (self.__get_midprice(closest_call), self.__get_midprice(closest_put))

    def __get_otm_strangle(self, date: str):
        calls = self.get_calls(date)
        puts = self.get_puts(date)
        price = self.get_current_price()
        
        otm_call = calls[calls["strike"] > price].iloc[0]
        otm_put = puts[puts["strike"] < price].iloc[-1]
        
        return (self.__get_midprice(otm_call), self.__get_midprice(otm_put))

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

    def __get_butterfly(self, date: str, strike1, strike2, strike3):
        calls = self.get_calls(date)
        strikes = calls["strike"].tolist()

        if not (strike1 in strikes and strike2 in strikes and strike3 in strikes):
            print("Strikes: \n" + str(strikes))
            raise ValueError("Strikes must be in the option chain")
        strike1_index = strikes.index(strike1)
        strike2_index = strikes.index(strike2)
        strike3_index = strikes.index(strike3)
        if not (strike1_index + 1 == strike2_index and strike2_index + 1 == strike3_index):
            print("Strikes: \n" + str(strikes))
            raise ValueError("Strikes must be next to each other")
        if not (strike2 - strike1 == strike3 - strike2):
            raise ValueError("Strike values must be equidistant")
        if calls[calls["strike"] == strike1]["volume"].iloc[0] < 10:
            raise ValueError(f"Strike {strike1} Volume must be at least 10")
        if calls[calls["strike"] == strike2]["volume"].iloc[0] < 10:
            raise ValueError(f"Strike {strike2} Volume must be at least 10")
        if calls[calls["strike"] == strike3]["volume"].iloc[0] < 10:
            raise ValueError(f"Strike {strike3} Volume must be at least 10")
        
        one_longcall = self.__get_midprice(calls[calls["strike"] == strike1].iloc[0])
        two_shortcall = self.__get_midprice(calls[calls["strike"] == strike2].iloc[0])
        second_longcall = self.__get_midprice(calls[calls["strike"] == strike3].iloc[0])

        return round((one_longcall - (2 * two_shortcall) + second_longcall), 2)