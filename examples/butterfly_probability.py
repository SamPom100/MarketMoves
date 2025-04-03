from autohedge import Stock

# SPY Implied Moves
spy = Stock("SPY")
spy_dates = spy.get_option_dates()
spy.plot_butterfly_probabilities(spy_dates[12])

# TSLA Implied Moves
tsla = Stock("TSLA")
tsla_dates = tsla.get_option_dates()
tsla.plot_butterfly_probabilities(tsla_dates[5])