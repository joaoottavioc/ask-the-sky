# generate_keys.py
import streamlit_authenticator as stauth

# Lista de senhas que você quer usar
passwords_to_hash = ['abc', 'def']  # Coloque as senhas que deseja aqui

hashed_passwords = stauth.Hasher(passwords_to_hash).generate()
print(hashed_passwords)