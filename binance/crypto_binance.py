import click
import pandas as pd
import os
import time

from binance.client import Client

@click.command()
@click.option('--pm', default=0.01, help='Profit Margin')
@click.option('--ci', default=60, help='Check interval in seconds')

def trade_coins(pm, ci):
    
    if os.path.isdir('crypto-data'):
        pass
    else:
        os.mkdir('crypto-data')
        
    if os.path.exists('cypto-data/crypto-log.txt'):
        os.remove('cypto-data/crypto-log.txt')
    else:
        pass

    file = open('crypto-data/crypto-log.txt', 'w')

    api_key = 'XzkhEsU0HHARj880CT9Ck4tlsD4WZaQSbsbdAy7kXvMp3yOjzKdRbCZdGAeQ2YhA'

    api_secret = 'xfg149pnCFuhWHOtgHOmgwCox4DkGRv66FI0kN5VNY3FLuhMhsfhJxJRMIGPeGiQ'

    client = Client(api_key, api_secret)

    print('--- Client Instantiated ---')
    file.write('--- Client Instantiated ---\n')

    pd.options.mode.chained_assignment = None

    coins = client.get_all_coins_info()

    print('--- Coins retrieved ---')
    file.write('--- Coins retrieved ---\n')

    coins_dataframe = pd.DataFrame(columns=['coin','trading','isLegalMoney'])

    for coin in coins:
        coins_dataframe = coins_dataframe.append({'coin': coin['coin'], 'trading': coin['trading'],'isLegalMoney': coin['isLegalMoney']}, ignore_index=True) 

    coins_dataframe = coins_dataframe[coins_dataframe.trading > 0 ]
    coins_dataframe = coins_dataframe[coins_dataframe.isLegalMoney == 0]

    print('--- Retrieving Trade Fees ---')
    file.write('--- Retrieving Trade Fees ---\n')

    coins_dataframe['trade_fee'] = coins_dataframe.coin.apply(lambda x: client.get_trade_fee(symbol=x+'USDT'))

    coins_dataframe.trade_fee = coins_dataframe.trade_fee.apply(lambda x: x if len(x)> 0 else None)
    coins_dataframe = coins_dataframe[coins_dataframe.trade_fee.astype(str) != 'None']

    coins_dataframe['trade_symbol'] = coins_dataframe.trade_fee.apply(lambda x: x[0]['symbol'])

    print('--- Trade fees retrieved ---')
    file.write('--- Trade fees retrieved ---\n')

    coins_dataframe.reset_index(inplace=True,drop=True)

    coins_dataframe['profit'] = 0

    coins_dataframe['gained'] = 0

    coins_dataframe['times_it_sold'] = 0

    coins_dataframe['coin_status'] = 'initialized'

    print('--- Statistics initialized ---')
    file.write('--- Statistics initialized ---\n')

    initial_buying_prices = os.path.exists('crypto-data/initial_buying_prices.csv')

    coins_dataframe['initial_buy_price'] = None
    coins_dataframe['initial_buy_cost'] = None
    coins_dataframe.reset_index(drop=True,inplace=True)

    if initial_buying_prices:
        initial_buying_prices = pd.read_csv('crypto-data/initial_buying_prices.csv')
        for coin in initial_buying_prices.coin.values:
            if coin in coins_dataframe.coin.values:
                index = coins_dataframe[coins_dataframe.coin == coin].index[0]
                index_initial_buying_prices = initial_buying_prices[initial_buying_prices.coin == coin].index[0]
                coins_dataframe.loc[index, 'initial_buy_price'] = initial_buying_prices.loc[index_initial_buying_prices,'initial_buy_price']
                coins_dataframe.loc[index, 'initial_buy_cost'] = initial_buying_prices.loc[index_initial_buying_prices,'initial_buy_cost']
    else:
        prices = client.get_all_tickers()
        for price in prices:
            if price['symbol'] in coins_dataframe.trade_symbol.values:
                index = coins_dataframe[coins_dataframe.trade_symbol == price['symbol']].index[0]
                coins_dataframe.loc[index,'initial_buy_price'] = float(price['price'])
                coins_dataframe.loc[index,'initial_buy_cost'] = float(coins_dataframe.loc[index,'trade_fee'][0]['makerCommission']) * float(price['price'])

        coins_dataframe[['coin','initial_buy_price','initial_buy_cost']].to_csv('crypto-data/initial_buying_prices.csv',index=False)
        
    print('--- Initial prices retrieved ---')
    file.write('--- Initial prices retrieved ---\n')

    print('--- Starting the updating of the prices loop ---')
    file.write('--- Starting the updating of the prices loop ---\n')

    coins_sold_history = os.path.exists('crypto-data/coins_sold_history.csv')
    if coins_sold_history:
        df_coins_sold = pd.read_csv('crypto-data/coins_sold_history.csv')
    else:
        df_coins_sold = pd.DataFrame(columns=['coin','initial_buy_price','initial_buy_cost','out_price','estimated_cost', 'profit'])

    coins_rebought_history = os.path.exists('crypto-data/coins_rebought_history.csv')
    if coins_rebought_history:
        df_coins_rebought = pd.read_csv('crypto-data/coins_rebought_history.csv')
    else:
        df_coins_rebought = pd.DataFrame(columns=['coin','initial_buy_price','initial_buy_cost','rebought_at', 'rebuy_cost', 'gained'])

    start = time.time()
    count = float(0)
    while 1:
        try:
            if int(((time.time() - start))) >= ci:
                prices = client.get_all_tickers()
                for price in prices:
                    if price['symbol'] in coins_dataframe.trade_symbol.values:
                        index = coins_dataframe[coins_dataframe.trade_symbol == price['symbol']].index[0]
                        coins_dataframe.loc[index,'updated_price'] = float(price['price'])
                        coins_dataframe.loc[index,'out_price'] = float(coins_dataframe.loc[index,'trade_fee'][0]['takerCommission']) * float(price['price'])
                        
                        if coins_dataframe.loc[index,'coin_status'] == 'initialized':
                            coins_dataframe.loc[index,'estimated_cost'] = ((float(coins_dataframe.loc[index,'initial_buy_cost']) + float(coins_dataframe.loc[index,'out_price']) + float(coins_dataframe.loc[index,'initial_buy_price'])))
                        
                        if coins_dataframe.loc[index,'coin_status'] == 'rebought':
                            coins_dataframe.loc[index,'estimated_cost'] = (float(coins_dataframe.loc[index,'rebuy_cost']) + float(coins_dataframe.loc[index,'out_price']) + float(coins_dataframe.loc[index,'rebought_at']))

                        if coins_dataframe.loc[index,'coin_status'] != 'sold':
                            coins_dataframe.loc[index,'profit'] = coins_dataframe.loc[index,'updated_price'] - float(coins_dataframe.loc[index,'estimated_cost'])

                            if coins_dataframe.loc[index,'profit'] >= pm:
                                coins_dataframe.loc[index,'coin_status'] = 'sold'
                                coins_dataframe.loc[index,'times_it_sold'] += float(1)
                                df_coins_sold = df_coins_sold.append({'coin': price['symbol'], 'initial_buy_price': coins_dataframe.loc[index,'initial_buy_price'], 
                                        'initial_buy_cost': coins_dataframe.loc[index,'initial_buy_cost'], 'out_price': price['price'], 'estimated_cost': coins_dataframe.loc[index,'estimated_cost'], 
                                            'profit': coins_dataframe.loc[index,'profit']}, ignore_index=True)
                                df_coins_sold.to_csv('crypto-data/coins_sold_history.csv', index=False)
                                
                                print('--- SOLD {} ---'.format(price['symbol']))
                                file.write('--- SOLD {} ---\n'.format(price['symbol']))
                        

                prices = client.get_all_tickers()
                for price in prices:
                    if price['symbol'] in coins_dataframe.trade_symbol.values:
                        index = coins_dataframe[coins_dataframe.trade_symbol == price['symbol']].index[0]
                        if coins_dataframe.loc[index,'coin_status'] == 'sold':
                            if float(price['price']) <= float(coins_dataframe.loc[index,'initial_buy_price']):
                                coins_dataframe.loc[index,'gained'] += float(coins_dataframe.loc[index,'profit'])
                                coins_dataframe.loc[index,'coin_status'] = 'rebought'
                                coins_dataframe.loc[index,'rebought_at'] = (float(price['price']))
                                coins_dataframe.loc[index,'rebuy_cost'] = float(coins_dataframe.loc[index,'trade_fee'][0]['makerCommission']) * (float(price['price']))
                                df_coins_rebought = df_coins_rebought.append({'coin': price['symbol'], 'initial_buy_price': coins_dataframe.loc[index, 'initial_buy_price'], 
                                            'initial_buy_cost': coins_dataframe.loc[index, 'initial_buy_cost'], 
                                            'total_initial_buy_cost': float(coins_dataframe.loc[index, 'initial_buy_price']) + float(coins_dataframe.loc[index, 'initial_buy_cost']),
                                            'rebought_at': coins_dataframe.loc[index,'rebought_at'], 
                                            'rebuy_cost':coins_dataframe.loc[index,'rebuy_cost'],
                                            'total_rebuy_cost': float(coins_dataframe.loc[index,'rebought_at']) + float(coins_dataframe.loc[index,'rebuy_cost']),
                                            'gained': coins_dataframe.loc[index,'gained']}, ignore_index=True)
                                df_coins_rebought.to_csv('crypto-data/coins_rebought_history.csv', index=False)
                                print('--- REBOUGHT {} ---'.format(price['symbol']))
                                file.write('--- REBOUGHT {} ---\n'.format(price['symbol']))

                start = time.time()
                count += float(ci/60)
                coins_dataframe.to_csv('crypto-data/export_coins.csv', index=False)

                print('--- DataFrame export updated ( Count {} )---'.format(count))
                file.write('--- DataFrame export updated ( Count {} )---\n'.format(count))
                file.close()
                file = open('crypto-data/crypto-log.txt', 'w')

        except Exception as e:

            print('--- Exception received ---')
            print('{}'.format(e))
            print('--- Restarting updating the prices ---')

            file.write('--- Exception received ---\n')
            file.write('{}\n'.format(e))
            file.write('--- Restarting updating the prices ---\n')


if __name__ == '__main__':
    trade_coins()

