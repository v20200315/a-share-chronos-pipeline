import streamlit as st


def main() -> None:
    st.set_page_config(
        page_title='Market Data Pipeline',
        layout='wide',
    )

    st.title('Market Data Pipeline')
    st.subheader('Hello, Streamlit!')
    st.write('This is the frontend entrypoint for `market_data_pipeline`.')


if __name__ == '__main__':
    main()
