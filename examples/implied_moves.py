from autohedge import Stock

print("VOO Implied Moves")
voo = Stock("VOO")
voo_moves = voo.get_expected_moves_all()
for move in voo_moves:
    print(f"{move}: {voo_moves[move]}%")

print("\n\nMSFT Implied Moves")
msft = Stock("MSFT")
msft_moves = msft.get_expected_moves_all()
for move in msft_moves:
    print(f"{move}: {msft_moves[move]}%")