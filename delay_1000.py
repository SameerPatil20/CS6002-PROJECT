# main.py (Simulation loop and analysis)
import random
import numpy as np
import csv
from traders import Trader
from market import MarketCall
import matplotlib.pyplot as plt
T = 12000           # trading horizon
N_Manual_Trader = 800
qmax = 10           # inventory bound
r_bar = 10000       # long-run mean of fundamental
kappa = 0.05        # mean-reversion
sigma_s = 1e6       # fundamental shock variance
sigma_PV = 5e6      # private-value variance
lambda_s = 0.004    # slow traders' reentry rate
lambda_f = 0.5      # HFT reentry rate
qmax_HFT = 10*qmax
call_interval = 1
delays = [1000]
effi=[]
interval=[]
plt.figure(figsize=(8, 6))
for delay in delays:
    for jump in range(1,2002,100):
        call_interval=jump
        traders = {}
        for i in range(N_Manual_Trader):
            theta_vals = np.random.normal(0, np.sqrt(sigma_PV), 2*qmax+1)
            theta_vals.sort()
            traders[i] = Trader(id=i, is_fast=False, arrival_rate=lambda_s,
                                qmax=qmax, theta=theta_vals,
                                R_min=0, R_max=250, eta=1.0)
        # High-frequency trader
        theta_vals = np.random.normal(0, np.sqrt(sigma_PV), 2*qmax_HFT+1)
        theta_vals.sort()
        traders[N_Manual_Trader] = Trader(id=N_Manual_Trader, is_fast=True, arrival_rate=lambda_f,
                            qmax=qmax_HFT, theta=theta_vals,
                            R_min=0, R_max=250, eta=1.0)

        market_type = 'CALL'
        market = MarketCall(call_interval)

        # Prepare CSV writers
        tf = open('trades.csv', 'w', newline='')
        trade_writer = csv.writer(tf)
        trade_writer.writerow(['time','buyer_id','seller_id','price','buyer_pos_before','seller_pos_before'])
        bf = open('orderbook_snapshots.csv', 'w', newline='')
        book_writer = csv.writer(bf)
        book_writer.writerow(['time','market_type','bids','asks'])

        # Data buffers for metrics
        total_trades = 0
        spreads = []
        price_series = []
        trade_records = []  

        # Initialize fundamental series
        r = np.zeros(T+1); r[0] = r_bar

        for t in range(1, T+1):
            
            shock = np.random.normal(0, np.sqrt(sigma_s))
            r[t] = max(0, kappa*r_bar + (1-kappa)*r[t-1] + shock)

            arrivals = []
            slow_arr = np.random.binomial(N_Manual_Trader, lambda_s)
            if slow_arr>0: arrivals += list(np.random.choice(N_Manual_Trader, slow_arr, replace=False))
            if random.random() < lambda_f: arrivals.append(N_Manual_Trader)
            random.shuffle(arrivals)
            bids = sorted(market.buy_orders, key=lambda x: x[0], reverse=True)
            asks = sorted(market.sell_orders, key=lambda x: x[0])
            book_writer.writerow([t, market_type, bids, asks])
            # Best quotes
            best_bid = best_ask = None
                
            for i in range(N_Manual_Trader):
                tr = traders[i]
                tr.left_order[t-1]=None
                if(tr.left_order.get(t,None)!=None):
                    if tr.outstanding_order:
                        typ, price = tr.outstanding_order
                        if typ=='buy_limit': market.buy_orders=[(p,j) for (p,j) in market.buy_orders if j!=i]
                        else: market.sell_orders=[(p,j) for (p,j) in market.sell_orders if j!=i]
                        tr.outstanding_order=None
                    temp = tr.left_order[t]
                    if(temp is None):
                        continue
                    
                    otype,price=temp
                    if(tr.position >=tr.qmax and otype=="buy_limit"):
                        continue
                    if(tr.position <= -tr.qmax and otype=="sell_limit"):
                        continue
                    market.add_order(tr, otype, price)
                    tr.outstanding_order=(otype,price)
            # Process arrivals
            for i in arrivals:
                tr = traders[i]
                # Cancel previous
                if tr.is_fast and tr.outstanding_order:
                    typ, price = tr.outstanding_order
                    if typ=='buy_limit': market.buy_orders=[(p,j) for (p,j) in market.buy_orders if j!=i]
                    else: market.sell_orders=[(p,j) for (p,j) in market.sell_orders if j!=i]
                    tr.outstanding_order=None
                    tr.stored_order=None
                r_hat=(1-(1-kappa)**(T-t))*r_bar + (1-kappa)**(T-t)*r[t]
                temp = tr.decide_order(r_hat, best_bid, best_ask, t, delay)
                if(temp is None):
                    continue
                otype,price=temp
                market.add_order(tr, otype, price); tr.outstanding_order=(otype,price)
            # CALL clearing
            if t>=market.next_clear:
                market.time=t
                market.clear_market(traders)
                for rec in market.trade_log:
                    trade_writer.writerow(rec); trade_records.append(rec)
                    total_trades+=1; price_series.append(rec[3])
                market.trade_log.clear(); market.next_clear+=market.interval

        # Close CSVs
        tf.close(); bf.close()

        # Metrics
        prices=price_series; diffs=np.diff(prices) if len(prices)>1 else np.array([])
        price_vol=np.std(diffs) if diffs.size>0 else 0.0
        avg_spread=np.mean(spreads) if spreads else None; ntr=total_trades
        # Social surplus
        total_surplus=market.social_surplus
        # Efficiency
        bv,sv=[],[]
        for tr in traders.values():
            for q in range(1,qmax+1): bv.append(r_bar+tr.theta[q+qmax])
            for q in range(0,-qmax,-1): sv.append(r_bar+tr.theta[q+qmax])
        bv.sort(reverse=True); sv.sort()
        opt=sum(b-s for b,s in zip(bv,sv) if b>=s)
        eff=total_surplus/opt if opt>0 else None
        # Trader utilities
        final_r=r[T]; slow_sum=0; hft_sum=0
        for _, b, s, p, bq, sq in trade_records:
            buyer = traders[b]
            seller = traders[s]
            tb = buyer.theta[bq+1 + qmax]
            ts = seller.theta[sq + qmax]
            bs = (final_r + tb) - p
            ss = p - (final_r + ts)
            if buyer.is_fast:
                hft_sum += bs
            else:
                slow_sum += bs
            if seller.is_fast:
                hft_sum += ss
            else:
                slow_sum += ss
        effi.append(eff*100)
        interval.append(call_interval)
        print(delay,jump,eff,end="\r")
        
    plt.plot(interval, effi, linewidth=2, marker='o', label=f'Delay {delay}')
    max_index = effi.index(max(effi))
    x_at_max_y = interval[max_index]
plt.xlabel('Batch Interval')
plt.ylabel('Efficiency')
plt.title('Combined Plot')
plt.grid(True)
plt.legend()
plt.savefig('combined_plot.png', dpi=300)
plt.show()