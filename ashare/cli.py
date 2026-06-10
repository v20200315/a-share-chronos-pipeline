import argparse

from ashare.metadata.validator import MetadataValidator
from ashare.metadata.manager import MetadataManager


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('command')

    args = parser.parse_args()

    manager = MetadataManager()

    if args.command == 'refresh':
        df = manager.refresh()
        MetadataValidator.validate_stock_basic(df)

    elif args.command == 'load':
        df = manager.load()
        print(df.head())


if __name__ == '__main__':
    main()
