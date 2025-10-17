import streamlit as st

st.title("My First Streamlit App")
st.write("Hello, world! Welcome to your app.")

# Add a slider
number = st.slider("Pick a number", 0, 100, 50)
st.write(f"You selected: {number}")

# Add a button
if st.button("Say hello"):
    st.write("Hello! 👋")