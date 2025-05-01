class MarketCall:
    def __init__(self, interval):
        self.interval = interval
        self.time = 0
        self.buy_orders = []
        self.sell_orders = []
        self.trade_log = []
        self.social_surplus = 0.0
        self.next_clear = interval

    def add_order(self, trader, order_type, price):
        if order_type == "buy_limit":
            self.buy_orders.append((price, trader.id))
        else:
            self.sell_orders.append((price, trader.id))

    def clear_market(self, traders):
        # Sort and match all bids ≥ asks
        self.buy_orders.sort(key=lambda x: x[0], reverse=True)
        self.sell_orders.sort(key=lambda x: x[0])
        b=0; s=0
        while b < len(self.buy_orders) and s < len(self.sell_orders):
            buy_price, buyer_id = self.buy_orders[b]
            sell_price, seller_id = self.sell_orders[s]
            if buy_price >= sell_price:
                trade_price = 0.5*(buy_price + sell_price)
                buyer = traders[buyer_id]; seller = traders[seller_id]
                b_q = buyer.position; s_q = seller.position
                self.trade_log.append((self.time, buyer_id, seller_id, trade_price, b_q, s_q))
                theta_b = buyer.theta[b_q+1 + buyer.qmax]
                theta_s = seller.theta[s_q + seller.qmax]
                self.social_surplus += (theta_b - theta_s)
                buyer.position += 1
                seller.position -= 1
                b += 1; s += 1
            else:
                break
        # Remove executed orders
        self.buy_orders = self.buy_orders[b:]
        self.sell_orders = self.sell_orders[s:]

    def step(self, traders):
        self.time += 1
        if self.time >= self.next_clear:
            self.clear_market(traders)
            self.next_clear += self.interval
