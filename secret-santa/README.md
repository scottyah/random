# 🎅 Secret Santa Application

A festive Next.js application for managing Secret Santa gift exchanges with Supabase authentication and database. Features a fun, Christmassy theme with snowflakes, festive colors, and holiday cheer! 🎄✨

## Features

- 🔐 **User Authentication** - Secure login with Supabase Auth
- 🎁 **Wishlist Management** - Users can create and edit their own wishlists
- 🎯 **Assignment Viewing** - See who you're Secret Santa for
- ✅ **Purchase Tracking** - Mark items as purchased (only you can see)
- 💰 **Price Tracking** - Track estimated gift prices
- ⏰ **Countdown Timer** - Days remaining until the exchange
- 👫 **Couples Protection** - Algorithm ensures couples don't get each other
- 🎨 **Festive Theme** - Christmas-themed UI with snowflakes, gradients, and animations

## Tech Stack

- **Frontend**: Next.js 15, React, TypeScript, Tailwind CSS
- **Backend**: Supabase (PostgreSQL + Auth)
- **Package Manager**: npm (or Bun for faster performance)
- **Deployment**: Vercel (recommended)

## Prerequisites

- Node.js 18+ or Bun 1.0+ installed
- A Supabase account ([signup here](https://supabase.com))
- npm, yarn, or bun package manager

## Setup Instructions

### 1. Clone and Install Dependencies

**Using npm:**
```bash
npm install
```

**Using Bun (faster):**
```bash
# Install Bun if you haven't already
curl -fsSL https://bun.sh/install | bash

# Install dependencies
bun install
```

### 2. Set Up Supabase

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **Project Settings > API** and copy:
   - Project URL
   - Anon/Public Key

### 3. Configure Environment Variables

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Edit `.env.local` with your Supabase credentials:

```env
NEXT_PUBLIC_SUPABASE_URL=your-project-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_SECRET_SANTA_DATE=2025-12-25
```

### 4. Set Up the Database

1. In your Supabase project, go to **SQL Editor**
2. Open `DATABASE_SCHEMA.md` in this repository
3. Copy and execute the SQL commands in order to:
   - Create tables (profiles, assignments, wishlist_items)
   - Set up Row Level Security policies
   - Create triggers and functions

### 5. Configure Participants

Edit `lib/participants.ts` to add your participants and define couples:

```typescript
export const participants: Participant[] = [
  { name: "Alice Johnson", email: "alice@example.com" },
  { name: "Bob Smith", email: "bob@example.com" },
  // Add more participants...
]

export const couples: Couple[] = [
  { person1Email: "alice@example.com", person2Email: "bob@example.com" },
  // Add more couples...
]
```

### 6. Create User Accounts

**Option A: Manual Creation in Supabase Dashboard**
1. Go to **Authentication > Users** in Supabase
2. Click **Add User**
3. Enter email and password for each participant
4. Users can now login with these credentials

**Option B: Use Supabase CLI** (advanced)
```bash
# Install Supabase CLI
npm install -g supabase

# Create users programmatically
# (You'll need to write a script for this)
```

### 7. Generate Secret Santa Assignments

After creating user accounts, generate assignments:

```bash
# Start the dev server
npm run dev

# In another terminal, call the admin API
curl -X POST http://localhost:3000/api/admin/generate-assignments
```

This will:
- Generate assignments using the algorithm
- Ensure couples don't get each other
- Store assignments in the database

### 8. Send Notifications (Optional - Stubbed)

To "send" notification emails (currently logs to console):

```bash
curl -X POST http://localhost:3000/api/admin/send-notifications
```

**Note**: Email functionality is currently stubbed. To implement real emails:
1. Choose an email service (SendGrid, Resend, etc.)
2. Update `lib/email.ts` with actual email sending logic
3. Add API keys to environment variables

## Running the Application

**Using npm:**
```bash
# Development
npm run dev

# Production build
npm run build
npm start
```

**Using Bun:**
```bash
# Development
bun run dev

# Production build
bun run build
bun start
```

Open [http://localhost:3000](http://localhost:3000) to access the application.

## Usage

### For Participants

1. **Login**: Navigate to `/login` and enter your credentials
2. **View Assignment**: See who you're Secret Santa for on the dashboard
3. **View Their Wishlist**: Browse your target's wishlist with prices and links
4. **Mark as Purchased**: Track which items you've bought (only you see this)
5. **Manage Your Wishlist**: Switch to "My Wishlist" tab to add/edit items
6. **Add Items**: Include title, description, price, and product URLs

### For Administrators

**Generate New Assignments**:
```bash
curl -X POST http://localhost:3000/api/admin/generate-assignments
```

**Send Notifications**:
```bash
curl -X POST http://localhost:3000/api/admin/send-notifications
```

**Important**: In production, you should protect these admin endpoints with authentication or run them locally only.

## File Structure

```
secret-santa/
├── app/
│   ├── api/admin/          # Admin API routes
│   ├── dashboard/          # Main dashboard page
│   ├── login/              # Login page
│   └── layout.tsx          # Root layout
├── components/
│   ├── WishlistEditor.tsx  # Component for editing own wishlist
│   └── TargetWishlist.tsx  # Component for viewing target's wishlist
├── lib/
│   ├── supabase/           # Supabase client utilities
│   ├── participants.ts     # Participant configuration
│   ├── secret-santa-algorithm.ts  # Assignment generation logic
│   ├── email.ts            # Email functions (stubbed)
│   └── types.ts            # TypeScript type definitions
├── DATABASE_SCHEMA.md      # Database setup SQL
├── .env.local              # Environment variables (create this)
└── README.md               # This file
```

## Security Considerations

- Row Level Security (RLS) is enabled on all tables
- Users can only see their own profile and wishlist
- Users can only see the wishlist of their assigned person
- Assignment data is protected - users only see who they give to
- Admin endpoints should be protected in production

## Troubleshooting

**"Invalid credentials" error**:
- Verify Supabase URL and keys in `.env.local`
- Check that users are created in Supabase Dashboard

**"No assignment found"**:
- Run the generate-assignments API endpoint
- Check that profiles exist for all participants

**Database errors**:
- Verify all SQL from `DATABASE_SCHEMA.md` was executed
- Check RLS policies are enabled

**Couples getting each other**:
- Verify couples are correctly defined in `lib/participants.ts`
- Re-run assignment generation

## Customization

### Change Event Date

Edit `.env.local`:
```env
NEXT_PUBLIC_SECRET_SANTA_DATE=2025-12-31
```

### Customize Colors

Edit Tailwind classes in components (primarily red/green Christmas theme)

### Add Real Email Service

1. Install email provider SDK (e.g., `npm install @sendgrid/mail`)
2. Update `lib/email.ts` with real implementation
3. Add API keys to `.env.local`

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT
