from models import CurrencyEnum


def total_summary_report(incomes, summary_title: str) -> str:
    totals = {currency.name: 0 for currency in CurrencyEnum}
    transaction_counts = {"KHR": 0, "USD": 0}

    for income in incomes:
        if income.currency in totals:
            transaction_counts[income.currency] += 1
            totals[income.currency] += income.amount
        else:
            totals[income.currency] = income.amount

    message = f"{summary_title}:\n\n"
    for currency in CurrencyEnum:
        code = currency.name
        symbol = currency.value
        total = totals.get(code, 0)
        format_string = "{:,.0f}" if code == "KHR" else "{:,.2f}"
        transaction_count = transaction_counts.get(code, 0)
        message += f"{symbol} ({code}): {format_string.format(total)} ចំនួនប្រតិបត្តិការសរុប​​: {transaction_count}\n"

    return message
