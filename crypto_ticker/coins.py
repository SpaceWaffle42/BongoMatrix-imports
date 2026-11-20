"""The coins on offer (CoinGecko's own ids) and the currencies to price them in."""
COINS = {
    "bitcoin": ("BTC", "Bitcoin"), "ethereum": ("ETH", "Ethereum"), "solana": ("SOL", "Solana"),
    "ripple": ("XRP", "XRP"), "cardano": ("ADA", "Cardano"), "dogecoin": ("DOGE", "Dogecoin"),
    "litecoin": ("LTC", "Litecoin"), "polkadot": ("DOT", "Polkadot"), "chainlink": ("LINK", "Chainlink"),
    "stellar": ("XLM", "Stellar"), "monero": ("XMR", "Monero"), "tether": ("USDT", "Tether"),
}
CURRENCIES = {"gbp": "£", "usd": "$", "eur": "€"}


def forms(value):
    """The ways to write a price, the exact one first: 67,412 then 67.4K  ·  182.40 then 182  ·  0.5123 then 0.512."""
    if value >= 1000:
        return [f"{value:,.0f}", f"{value / 1000:.1f}K" if value < 100_000 else f"{value / 1000:,.0f}K"]
    if value >= 1:
        return [f"{value:,.2f}", f"{value:,.0f}"]
    return [f"{value:.4f}", f"{value:.3f}"]


def money(value, sign="", fits=lambda text: True, exact=False):
    """A price with its sign, written the fullest way that ``fits`` (a test of the text). When none does: None if
    ``exact`` (the caller tries a smaller font), else the shortest form."""
    for text in forms(value)[:1 if exact else None]:
        if fits(sign + text):
            return sign + text
    return None if exact else sign + forms(value)[-1]
