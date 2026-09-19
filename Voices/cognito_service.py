"""
cognito_service.py
"""

import boto3
import base64
import hashlib
import hmac
import requests
from jose import jwt, JWTError
from django.conf import settings
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class CognitoService:
    def __init__(self):
        self.user_pool_id    = settings.AWS_COGNITO_USER_POOL_ID
        self.client_id       = settings.AWS_COGNITO_APP_CLIENT_ID
        self.client_secret   = settings.AWS_COGNITO_APP_CLIENT_SECRET
        self.region          = settings.AWS_COGNITO_REGION
        self.client = boto3.client('cognito-idp', region_name=self.region)

    def _secret_hash(self, username: str) -> str:
        msg = username + self.client_id
        dig = hmac.new(
            key=self.client_secret.encode('utf-8'),
            msg=msg.encode('utf-8'),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(dig).decode()

    @staticmethod
    def _escape_cognito_filter_value(value: str) -> str:
        return value.replace('\\', '\\\\').replace('"', '\\"')

    def _user_with_attribute_exists(self, attribute_name: str, attribute_value: str) -> bool:
        if not attribute_value:
            return False

        try:
            escaped = self._escape_cognito_filter_value(attribute_value)
            resp = self.client.list_users(
                UserPoolId=self.user_pool_id,
                Filter=f'{attribute_name} = "{escaped}"',
                Limit=1,
            )
            return bool(resp.get('Users'))
        except ClientError as e:
            logger.warning(
                "Cognito list_users failed for %s [%s]: %s",
                attribute_name,
                e.response['Error']['Code'],
                e.response['Error']['Message'],
            )
            return False

    def email_exists(self, email: str) -> bool:
        return self._user_with_attribute_exists('email', email)

    def phone_exists(self, phone_number: str) -> bool:
        return self._user_with_attribute_exists('phone_number', phone_number)

    def register_user(self, username: str, password: str, email: str,
                      phone_number: str, user_type: str, gender: str = 'not specified') -> dict:
        try:
            resp = self.client.sign_up(
                ClientId=self.client_id,
                SecretHash=self._secret_hash(username),
                Username=username,
                Password=password,
                UserAttributes=[
                    {'Name': 'email',            'Value': email},
                    {'Name': 'phone_number',     'Value': phone_number},
                    {'Name': 'name',             'Value': username},
                    {'Name': 'gender',           'Value': gender},
                    {'Name': 'custom:user_type', 'Value': user_type},
                ],
            )
            delivery = resp.get('CodeDeliveryDetails', {})
            return {
                'success': True,
                'delivery': {
                    'destination': delivery.get('Destination', ''),
                    'medium': delivery.get('DeliveryMedium', ''),
                    'attribute_name': delivery.get('AttributeName', ''),
                },
            }
        except ClientError as e:
            code = e.response['Error']['Code']
            msg  = e.response['Error']['Message']
            logger.error(f"Cognito register error [{code}]: {msg}")
            return {'success': False, 'error': msg, 'code': code}

    def confirm_email(self, username: str, code: str) -> dict:
        try:
            self.client.confirm_sign_up(
                ClientId=self.client_id,
                SecretHash=self._secret_hash(username),
                Username=username,
                ConfirmationCode=code,
            )
            return {'success': True}
        except ClientError as e:
            return {'success': False, 'error': e.response['Error']['Message']}

    def resend_confirmation_code(self, username: str) -> dict:
        try:
            resp = self.client.resend_confirmation_code(
                ClientId=self.client_id,
                SecretHash=self._secret_hash(username),
                Username=username,
            )
            delivery = resp.get('CodeDeliveryDetails', {})
            return {
                'success': True,
                'delivery': {
                    'destination': delivery.get('Destination', ''),
                    'medium': delivery.get('DeliveryMedium', ''),
                    'attribute_name': delivery.get('AttributeName', ''),
                },
            }
        except ClientError as e:
            return {'success': False, 'error': e.response['Error']['Message']}

    def authenticate_user(self, username: str, password: str) -> dict:
        try:
            resp = self.client.initiate_auth(
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password,
                    'SECRET_HASH': self._secret_hash(username),
                },
                ClientId=self.client_id,
            )
            if resp.get('ChallengeName'):
                return {
                    'success': False,
                    'challenge': resp['ChallengeName'],
                    'session': resp.get('Session'),
                    'challenge_params': resp.get('ChallengeParameters', {}),
                }
            tokens = resp['AuthenticationResult']
            return {
                'success': True,
                'access_token':  tokens['AccessToken'],
                'id_token':      tokens['IdToken'],
                'refresh_token': tokens['RefreshToken'],
            }
        except ClientError as e:
            code = e.response['Error']['Code']
            msg  = e.response['Error']['Message']
            logger.warning(f"Cognito auth error [{code}]: {msg}")
            return {'success': False, 'error': msg, 'code': code}

    def respond_to_sms_mfa(self, username: str, mfa_code: str, session: str) -> dict:
        try:
            resp = self.client.respond_to_auth_challenge(
                ClientId=self.client_id,
                ChallengeName='SMS_MFA',
                Session=session,
                ChallengeResponses={
                    'USERNAME': username,
                    'SMS_MFA_CODE': mfa_code,
                    'SECRET_HASH': self._secret_hash(username),
                },
            )
            tokens = resp['AuthenticationResult']
            return {
                'success': True,
                'access_token':  tokens['AccessToken'],
                'id_token':      tokens['IdToken'],
                'refresh_token': tokens['RefreshToken'],
            }
        except ClientError as e:
            return {'success': False, 'error': e.response['Error']['Message']}

    def verify_token(self, id_token: str) -> dict | None:
        try:
            jwks_url = (
                f"https://cognito-idp.{self.region}.amazonaws.com"
                f"/{self.user_pool_id}/.well-known/jwks.json"
            )
            keys = requests.get(jwks_url, timeout=5).json()['keys']
            payload = jwt.decode(
                id_token,
                keys,
                algorithms=['RS256'],
                audience=self.client_id,
            )
            return payload
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            return None

    def get_user(self, access_token: str) -> dict | None:
        try:
            resp = self.client.get_user(AccessToken=access_token)
            attrs = {a['Name']: a['Value'] for a in resp['UserAttributes']}
            return attrs
        except ClientError as e:
            logger.error(f"get_user error: {e}")
            return None

    def get_user_attribute_verification_code(self, access_token: str,
                                              attribute: str = 'phone_number') -> dict:
        try:
            self.client.get_user_attribute_verification_code(
                AccessToken=access_token,
                AttributeName=attribute,
            )
            return {'success': True}
        except ClientError as e:
            return {'success': False, 'error': e.response['Error']['Message']}

    def verify_user_attribute(self, access_token: str, attribute: str, code: str) -> dict:
        try:
            self.client.verify_user_attribute(
                AccessToken=access_token,
                AttributeName=attribute,
                Code=code,
            )
            return {'success': True}
        except ClientError as e:
            return {'success': False, 'error': e.response['Error']['Message']}

    def update_user_attributes(self, access_token: str, attributes: list[dict]) -> dict:
        try:
            self.client.update_user_attributes(
                AccessToken=access_token,
                UserAttributes=attributes,
            )
            return {'success': True}
        except ClientError as e:
            return {'success': False, 'error': e.response['Error']['Message']}

    def change_password(self, access_token: str, previous_password: str, proposed_password: str) -> dict:
        try:
            self.client.change_password(
                AccessToken=access_token,
                PreviousPassword=previous_password,
                ProposedPassword=proposed_password,
            )
            return {'success': True}
        except ClientError as e:
            return {'success': False, 'error': e.response['Error']['Message']}

    def refresh_tokens(self, username: str, refresh_token: str) -> dict:
        """Exchange a refresh token for a new access + ID token pair.
        Note: Cognito does not return a new refresh token on refresh."""
        try:
            resp = self.client.initiate_auth(
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token,
                    'SECRET_HASH': self._secret_hash(username),
                },
                ClientId=self.client_id,
            )
            tokens = resp['AuthenticationResult']
            return {
                'success': True,
                'access_token': tokens['AccessToken'],
                'id_token': tokens.get('IdToken', ''),
            }
        except ClientError as e:
            logger.warning(
                f"Token refresh failed [{e.response['Error']['Code']}]: "
                f"{e.response['Error']['Message']}"
            )
            return {'success': False, 'error': e.response['Error']['Message']}

    def sign_out(self, access_token: str) -> bool:
        try:
            self.client.global_sign_out(AccessToken=access_token)
            return True
        except ClientError as e:
            logger.error(f"sign_out error: {e}")
            return False

    def forgot_password(self, username: str) -> dict:
        try:
            self.client.forgot_password(
                ClientId=self.client_id,
                SecretHash=self._secret_hash(username),
                Username=username,
            )
            return {'success': True}
        except ClientError as e:
            return {'success': False, 'error': e.response['Error']['Message']}

    def confirm_forgot_password(self, username: str, code: str, new_password: str) -> dict:
        try:
            self.client.confirm_forgot_password(
                ClientId=self.client_id,
                SecretHash=self._secret_hash(username),
                Username=username,
                ConfirmationCode=code,
                Password=new_password,
            )
            return {'success': True}
        except ClientError as e:
            return {'success': False, 'error': e.response['Error']['Message']}
