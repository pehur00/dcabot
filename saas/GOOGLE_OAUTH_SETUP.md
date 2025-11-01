# Google OAuth Setup Guide

This guide explains how to set up Google OAuth for the DCA Bot SaaS platform.

## Overview

The platform supports Google OAuth as an alternative authentication method. Users can register and login using their Google account, with admin approval required before they can access the platform.

## Features

- **Sign in with Google** button on login page
- Automatic account creation for new Google users
- Account linking for existing email users
- Two-tier admin approval system:
  - Users can register via Google
  - Admin must approve before user can login
- Secure token handling using Authlib

## Setup Instructions

### 1. Create Google OAuth Client

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google+ API"
   - Click "Enable"
4. Create OAuth credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URIs:
     - For local development: `http://localhost:3030/auth/google/callback`
     - For production: `https://dcabot-saas-web.onrender.com/auth/google/callback`
   - Click "Create"
5. Copy the Client ID and Client Secret

### 2. Configure Environment Variables

Add the following environment variables to your deployment:

#### Local Development (.env file)
```bash
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

#### Production (Render.com)
1. Go to your Render dashboard
2. Select your web service
3. Go to "Environment" tab
4. Add environment variables:
   - Key: `GOOGLE_CLIENT_ID`, Value: `your_client_id_here`
   - Key: `GOOGLE_CLIENT_SECRET`, Value: `your_client_secret_here`

### 3. Restart the Application

After setting the environment variables, restart the Flask application to apply the changes.

## How It Works

### User Registration via Google

1. User clicks "Sign in with Google" on login page
2. User is redirected to Google for authentication
3. After successful authentication, user is redirected back to `/auth/google/callback`
4. System checks if user exists:
   - If email exists but no Google ID: Link Google account to existing user
   - If user doesn't exist: Create new user with `is_active = FALSE`
5. User sees success message and is redirected to login page
6. Admin must approve the user before they can login

### User Login via Google (After Approval)

1. User clicks "Sign in with Google" on login page
2. User is redirected to Google for authentication
3. After successful authentication, system checks `is_active` status
4. If approved (`is_active = TRUE`): User is logged in
5. If not approved: User sees "pending approval" message

### Security Features

- **Email Verification**: Only verified Google emails are accepted
- **Admin Approval**: All new users require admin approval (is_active field)
- **Secure Token Handling**: Uses Authlib for OAuth flow
- **Account Linking**: Existing users can link their Google account
- **HTTPS Enforcement**: Production redirect URI uses HTTPS

## Database Changes

The following fields were added to the `users` table:

```sql
google_id VARCHAR(255) UNIQUE       -- Google user ID
oauth_provider VARCHAR(20)          -- OAuth provider (e.g., 'google')
profile_picture_url TEXT            -- Google profile picture URL
password_hash VARCHAR(255)          -- Now nullable (OAuth users don't need password)
is_active BOOLEAN DEFAULT FALSE     -- Changed default to FALSE (admin approval required)
```

## API Endpoints

- `GET /auth/google` - Initiate Google OAuth login
- `GET /auth/google/callback` - Handle Google OAuth callback

## Troubleshooting

### "Google login is not configured" Error

This means the `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` environment variables are not set. Check that:
1. Environment variables are set correctly
2. Application was restarted after setting variables
3. No typos in variable names

### "Invalid redirect URI" Error

This means the redirect URI used doesn't match what's configured in Google Cloud Console. Make sure:
1. Redirect URIs are exactly the same (including protocol and port)
2. Both local and production URIs are added if needed

### Users Can't Login After Google Sign-Up

This is expected behavior - admin must approve new users first:
1. Login as admin
2. Go to admin panel (if implemented) or database
3. Set `is_active = TRUE` for the user
4. User can now login

## Production Deployment Notes

- Ensure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set in Render.com environment variables
- Verify the production redirect URI is exactly: `https://dcabot-saas-web.onrender.com/auth/google/callback`
- Test OAuth flow in production after deployment
