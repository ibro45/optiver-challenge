from math import ceil
from enum import Enum


class Instrument(Enum):
    Stock1 = 0
    Stock2 = 1
    Basket = 2


exchange = None
books = None


def get_exchange(refresh=False):
    if not refresh and exchange is not None:
        return exchange
    e = Exchange()
    a = e.connect()
    return e


def get_books(refresh=False):
    if not refresh and books is not None:
        return books
    instruments = [0, 1, 2]
    exchange = get_exchange()
    return [exchange.get_last_price_book(x) for x in instruments]


def get_asks_for_volume(instrument, volume=500):
    total_prices = [0 for x in range(volume+1)]
    current_volume = 0
    books = get_books()[instrument]
    for ask in books.asks:
        total_prices[:ask.volume+1] = (ask.price, current_volume)
        current_volume = ask.volume+1
    return total_prices


def get_bids_for_volume(instrument, volume=500):
    total_prices = [0 for x in range(volume+1)]
    current_volume = 0
    books = get_books()[instrument]
    for bid in books.bids:
        total_prices[:bid.volume+1] = (bid.price, current_volume)
        current_volume = bid.volume+1
    return total_prices


def get_best_ask_for_volume(instrument, volume):
    total_price = 0
    total_prices = get_asks_for_volume(instrument, volume)
    end = len(total_prices)
    start = total_prices[end][1]
    while start != 0:
        total_price += total_prices[end][0]*(end-start)
        end = start
        start = total_prices[end][1]
    total_price += total_prices[end][0]*(end)
    return total_price


def get_best_bids_for_volume(instrument, volume):
    total_price = 0
    total_prices = get_bids_for_volume(instrument, volume)
    end = len(total_prices)
    start = total_prices[end][1]
    while start != 0:
        total_price += total_prices[end][0]*(end-start)
        end = start
        start = total_prices[end][1]
    total_price += total_prices[end][0]*(end)
    return total_price


def get_best_current_ask(books, instrument):
    return books[instrument].asks[0]


def get_best_current_bid(books, instrument):
    return books[instrument].bids[0]


def ioc_or_limit_sell(price_when_bought, books, instrument):  # Ako smo od nekog kupili
    return "LIMIT" if get_best_current_bid(books, instrument) < price_when_bought else "IOC"


def ioc_or_limit_buy(price_when_sold, books, instrument):    # Ako smo nekom dužni
    return "LIMIT" if get_best_current_ask(books, instrument) < price_when_sold else "IOC"


def make_ioc_order(instrument, price, type, volume):
    exchange = get_exchange()
    exchange.insert_order(instrument, price=price,
                          volume=volume, side=type, order_type="ioc")


def make_ioc_order_at_current_best(instrument, type, volume):
    exchange = get_exchange()
    books = get_books()
    best = get_best_current_ask(
        books, instrument) if type == 'bid' else get_best_current_bid(books, instrument)
    exchange.insert_order(instrument, price=best,
                          volume=volume, side=type, order_type="ioc")


def make_limit_order(instrument, price, type, volume):
    exchange = get_exchange()
    return exchange.insert_order(instrument, price=price, volume=volume, side=type, order_type="limit")


def delete_limit_order(instrument, order_id):
    exchange = get_exchange()
    return exchange.delete_order(instrument_id=instrument, order_id=order_id)


def delete_limit_orders(instrument):
    exchange = get_exchange()
    return exchange.delete_orders(instrument_id=instrument)


def check_position(instrument):
    exchange = get_exchange()
    return exchange.get_positions()[instrument]


def calculate_buy_basket_profit(basket_ask, stock1_bid, stock2_bid, minimumVolume=0):
    if minimumVolume > 0:
        return (minimumVolume*stock1_bid.price + minimumVolume*stock2_bid.price)-(basket_ask.price*minimumVolume*2)
    return (stock1_bid.price*stock1_bid.volume + stock2_bid.price*stock2_bid.volume)-(basket_ask.price*basket_ask.volume*2)


def calculate_sell_basket_profit(basket_ask, stock1_bid, stock2_bid, minimumVolume=0):
    if minimumVolume > 0:
        return (basket_ask.price*minimumVolume*2)-(minimumVolume*stock1_bid.price + minimumVolume*stock2_bid.price)
    return (basket_ask.price*basket_ask.volume*2)-(stock1_bid.price*stock1_bid.volume + stock2_bid.price*stock2_bid.volume)


def calculate_best_buy_basket_profit(best_basket_ask, best_stock1_bid, best_stock2_bid):
    basket_volume = max(best_basket_ask.volume, 2)

    stock1_volume = best_stock1_bid.volume
    stock2_volume = best_stock2_bid.volume

    if stock1_volume == stock2_volume and basket_volume == (stock1_volume + stock2_volume):
        return calculate_buy_basket_profit(best_basket_ask, best_stock1_bid, best_stock2_bid)

    elif basket_volume > (stock1_volume + stock2_volume):
        minimum_stock_volume = min(stock1_volume, stock2_volume)
        minimum_volume_profit = calculate_buy_basket_profit(
            best_basket_ask, best_stock1_bid, best_stock2_bid, minimum_stock_volume)
        maximise_volume_profit = calculate_buy_basket_profit(best_basket_ask, get_best_bids_for_volume(Instrument.Stock1.value, volume=ceil(
            basket_volume/2)), get_best_bids_for_volume(Instrument.Stock2.value, volume=ceil(basket_volume/2)))
        if minimum_volume_profit >= maximise_volume_profit:
            return minimum_volume_profit, "minimum_volume"
        else:
            return maximise_volume_profit, "maximise_volume"


def calculate_best_sell_basket_profit(best_basket_bid, best_stock1_ask, best_stock2_ask):
    basket_volume = max(best_basket_bid.volume, 2)

    stock1_volume = best_stock1_ask.volume
    stock2_volume = best_stock2_ask.volume

    if stock1_volume == stock2_volume and basket_volume == (stock1_volume + stock2_volume):
        return calculate_sell_basket_profit(best_basket_bid, best_stock1_ask, best_stock2_ask)

    elif basket_volume > (stock1_volume + stock2_volume):
        minimum_stock_volume = min(stock1_volume, stock2_volume)
        minimum_volume_profit = calculate_sell_basket_profit(
            best_basket_bid, best_stock1_ask, best_stock2_ask, minimum_stock_volume)
        maximise_volume_profit = calculate_sell_basket_profit(best_basket_bid, get_best_ask_for_volume(Instrument.Stock1.value, volume=ceil(
            basket_volume/2)), get_best_ask_for_volume(Instrument.Stock2.value, volume=ceil(basket_volume/2)))
        if minimum_volume_profit >= maximise_volume_profit:
            return minimum_volume_profit, "minimum_volume"
        else:
            return maximise_volume_profit, "maximise_volume"


def calculate_profit(books):
    best_basket_ask = get_best_current_ask(books, Instrument.Basket.value)
    best_stock1_ask = get_best_current_ask(books, Instrument.Stock1.value)
    best_stock2_ask = get_best_current_ask(books, Instrument.Stock2.value)

    best_basket_bid = get_best_current_bid(books, Instrument.Basket.value)
    best_stock1_bid = get_best_current_bid(books, Instrument.Stock1.value)
    best_stock2_bid = get_best_current_bid(books, Instrument.Stock2.value)

    buy_basket_profit, how_to_order = calculate_buy_basket_profit(
        best_basket_ask, best_stock1_bid, best_stock2_bid)
    sell_basket_profit, how_to_order = calculate_sell_basket_profit(
        best_basket_bid, best_stock1_ask, best_stock2_ask)

    if buy_basket_profit > sell_basket_profit:
        if how_to_order == "minimum_volume":
            minimum_stock_volume = min(
                best_stock1_bid.volume, best_stock2_bid.volume)
            stock1_sell = make_ioc_order(
                Instrument.Stock1.value, best_stock1_bid.price, "ask", minimum_stock_volume)
            stock2_sell = make_ioc_order(
                Instrument.Stock2.value, best_stock2_bid.price, "ask", minimum_stock_volume)
            basket_buy = make_ioc_order(
                Instrument.Basket.value, best_basket_ask.price, "bid", minimum_stock_volume)
        else:
            basket_buy = make_ioc_order(
                Instrument.Basket.value, best_basket_ask.price, "bid", best_basket_ask.volume)
            stock1_position = check_position(Instrument.Stock1.value)
            stock2_position = check_position(Instrument.Stock2.value)
            while abs(stock1_position) != best_stock1_bid.volume:
                make_ioc_order_at_current_best(
                    Instrument.Stock1.value, 'ask', stock1_position-best_stock1_bid.volume)
            while abs(stock2_position) != best_stock2_bid.volume:
                make_ioc_order_at_current_best(
                    Instrument.Stock2.value, 'ask', stock2_position-best_stock2_bid.volume)
    else:
        if how_to_order == "minimum_volume":
            minimum_stock_volume = min(
                best_stock1_ask.volume, best_stock2_ask.volume)
            basket_sell = make_ioc_order(
                Instrument.Basket.value, best_basket_bid.price, "ask", minimum_stock_volume)
            stock1_buy = make_ioc_order(
                Instrument.Stock1.value, best_stock1_ask.price, "bid", minimum_stock_volume)
            stock2_buy = make_ioc_order(
                Instrument.Stock2.value, best_stock2_ask.price, "bid", minimum_stock_volume)

        else:
            basket_sell = make_ioc_order(
                Instrument.Basket.value, best_basket_bid.price, "ask", best_basket_bid.volume)
            stock1_position = check_position(Instrument.Stock1.value)
            stock2_position = check_position(Instrument.Stock2.value)
            while abs(stock1_position) != best_stock1_ask.volume:
                make_ioc_order_at_current_best(
                    Instrument.Stock1.value, 'bid', stock1_position-best_stock1_ask.volume)
            while abs(stock2_position) != best_stock2_ask.volume:
                make_ioc_order_at_current_best(
                    Instrument.Stock2.value, 'bid', stock2_position-best_stock2_ask.volume)
