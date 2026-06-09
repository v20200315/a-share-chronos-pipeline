import akshare as ak


def main():
    stock_sse_summary_df = ak.stock_sse_summary()
    print(stock_sse_summary_df)


if __name__ == '__main__':
    main()
