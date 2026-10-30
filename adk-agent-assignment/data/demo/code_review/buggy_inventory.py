"""DELIBERATELY BUGGY fixture: correctness and maintainability defects, no security bugs."""


def add_item(item, basket=[]):            # planted: mutable default
    basket.append(item)
    return basket


def remove_out_of_stock(items):
    for item in items:
        if item["qty"] == 0:
            items.remove(item)              # planted: mutation during iteration
    return items


def average_price(prices):
    return sum(prices) / len(prices)        # planted: ZeroDivisionError on []


def parse_quantity(raw):
    try:
        return int(raw)
    except:                                 # planted: bare except
        return 0


def status_label(code):
    if code is "A":                         # planted: identity comparison with literal
        return "active"
    return "inactive"
    print("unreachable")                    # planted: dead code


DEFAULTS = {"currency": "USD", "region": "us", "currency": "EUR"}   # planted: duplicate key


def apply_discount(price, discount):
    if discount == None:                    # planted: == None
        return price
    return price - price * discount
