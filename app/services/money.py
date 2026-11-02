"""One money formatter for every surface that prints a USD amount.

Thousands separators always; two decimals only when the amount has
cents; Arabic-Indic digits for Arabic. Mirrors RC.money in
app/static/common.js so cards, chat, the summary, WhatsApp and the
PDF all print the same string for the same number.
"""

_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"


def arabic_digits(text):
    return "".join(_ARABIC_DIGITS[int(c)] if c.isdigit() else c
                   for c in str(text))


def format_money(value, lang="en", symbol=True):
    """"$1,090.50" / "$155" / "١٥٥$"-free: the symbol always leads."""
    if value is None:
        return ""
    cents = int(round(float(value) * 100))
    whole, frac = divmod(abs(cents), 100)
    text = "{:,}".format(whole)
    if frac:
        text += ".%02d" % frac
    if cents < 0:
        text = "-" + text
    if lang == "ar":
        text = arabic_digits(text)
    return ("$" + text) if symbol else text
