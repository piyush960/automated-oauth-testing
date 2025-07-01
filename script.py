import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from oauthlib.oauth2 import WebApplicationClient
import requests
import tempfile
from urllib.parse import urlparse, parse_qs

with open("credentials.json", "r") as f:
    config = json.load(f)["web"]


CLIENT_ID = config["client_id"] or "YOUR_CLIENT_ID"
CLIENT_SECRET = config["client_secret"] or "YOUR_CLIENT_SECRET"
AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = config["token_uri"]
REDIRECT_URI = config["redirect_uris"][0]
SCOPE = "openid email profile"
PROTECTED_RESOURCE_URL = "https://www.googleapis.com/oauth2/v1/userinfo?alt=json"


USERNAME = os.environ.get("OAUTH_USERNAME", "YOUR_TEST_GMAIL_USERNAME")
PASSWORD = os.environ.get("OAUTH_PASSWORD", "YOUR_TEST_GMAIL_PASSWORD")

"""
Uses undetected-chromedriver to automate login and consent,
and returns the authorization code.
"""
def get_authorization_code_stealth():
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')

    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--window-size=1920,1080")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    temp_profile = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={temp_profile}")


    client = WebApplicationClient(CLIENT_ID)
    authorization_request_url = client.prepare_request_uri(
        AUTHORIZATION_URL,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        access_type="offline",
        prompt="consent"
    )

    with uc.Chrome(options=options) as driver:
        driver.get(authorization_request_url)

        try:
            # email
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            email_input.send_keys(USERNAME)

            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "identifierNext"))
            )
            next_button.click()
            time.sleep(2)

            # password
            password_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "Passwd"))
            )
            password_input.send_keys(PASSWORD)

            password_next = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "passwordNext"))
            )
            password_next.click()
            time.sleep(3)

        except Exception as e:
            print(f"An error occurred during login automation: {e}")
            driver.save_screenshot("login_error.png")
            driver.quit()
            return None

        # handle consent screen (for google)
        try:
            consent_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[text()="Continue"]'))
            )
            consent_button.click()
        except:
            pass

        WebDriverWait(driver, 10).until(EC.url_contains(REDIRECT_URI))
        redirected_url = driver.current_url
        parsed_url = urlparse(redirected_url)
        authorization_code = parse_qs(parsed_url.query).get("code", [None])[0]

    return authorization_code


"""Exchanges the authorization code for access and refresh tokens."""
def exchange_code_for_tokens(authorization_code):
    client = WebApplicationClient(CLIENT_ID)
    token_request_body = client.prepare_request_body(
        code=authorization_code,
        redirect_uri=REDIRECT_URI,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )
    response = requests.post(TOKEN_URL, data=token_request_body, headers={
        "Content-Type": "application/x-www-form-urlencoded"
    })
    return response.json()


"""Uses the access token to get data from a protected resource."""
def access_protected_resource(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(PROTECTED_RESOURCE_URL, headers=headers)
    return response.json()


"""Uses the refresh token to get a new access token."""
def refresh_access_token(refresh_token):
    client = WebApplicationClient(CLIENT_ID)
    refresh_token_body = client.prepare_refresh_body(refresh_token=refresh_token, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    response = requests.post(TOKEN_URL, data=refresh_token_body, headers={
        "Content-Type": "application/x-www-form-urlencoded"
    })
    return response.json()


"""
Main function to run the automated OAuth 2.0 test.
"""
def main():
    print("\n\n--- Starting OAuth 2.0 Authorization Code Grant Test in Stealth Mode ---\n\n")

    print("Step 1: Automating browser login to get authorization code...")
    auth_code = get_authorization_code_stealth()
    if not auth_code:
        print("Failed to retrieve authorization code.")
        return
    print(f"Successfully retrieved authorization code: {auth_code[:20]}...")

    print("\n\nStep 2: Exchanging authorization code for tokens...")
    tokens = exchange_code_for_tokens(auth_code)
    if "error" in tokens:
        print(f"Error exchanging code for tokens: {tokens}")
        return
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    print("Successfully exchanged for tokens.")
    print(f"Access Token: {access_token[:20]}...")
    if refresh_token:
        print(f"Refresh Token: {refresh_token[:20]}...")

    print("\n\nStep 3: Accessing a protected resource with the access token...")
    user_info = access_protected_resource(access_token)
    if "error" in user_info:
        print(f"Error accessing protected resource: {user_info.get('error', {}).get('message')}")
    else:
        print("Successfully accessed protected resource.")
        print("User Info:", user_info)

    if refresh_token:
        print("\n\n--- Starting OAuth 2.0 Refresh Token Grant Test ---\n\n")
        print("Step 4: Refreshing the access token...")
        new_tokens = refresh_access_token(refresh_token)
        if "error" in new_tokens:
            print(f"Error refreshing access token: {new_tokens}")
            return
        new_access_token = new_tokens.get("access_token")
        print("Successfully refreshed the access token.")
        print(f"New Access Token: {new_access_token[:20]}...")

        print("\n\nStep 5: Accessing the protected resource with the new access token...")
        new_user_info = access_protected_resource(new_access_token)
        if "error" in new_user_info:
            print(f"Error accessing protected resource with new token: {new_user_info.get('error', {}).get('message')}")
        else:
            print("Successfully accessed protected resource with the new access token.")
            print("User Info:", new_user_info)

    print("\n\n--- OAuth 2.0 Automated Test Completed ---\n\n")

if __name__ == "__main__":
    if "YOUR_CLIENT_ID" in CLIENT_ID or "YOUR_CLIENT_SECRET" in CLIENT_SECRET:
        print("Configure your CLIENT_ID and CLIENT_SECRET.")
    elif "YOUR_TEST_GMAIL_USERNAME" in USERNAME or "YOUR_TEST_GMAIL_PASSWORD" in PASSWORD:
        print("Configure your USERNAME and PASSWORD.")
    else:
        main()