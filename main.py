import akshare as ak


def main():
    df = ak.stock_zh_a_spot_em()
    print(df.head(5).to_string())


if __name__ == '__main__':
    main()
