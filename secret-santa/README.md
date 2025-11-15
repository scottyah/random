# 🎅 Secret Santa Application

A festive Next.js application for managing Secret Santa gift exchanges with SQLite database and session-based authentication. Features a fun, Christmassy theme with snowflakes, festive colors, and holiday cheer! 🎄✨

## Features

- 🔐 **User Authentication** - Secure session-based login
- 🎁 **Wishlist Management** - Users can create and edit their own wishlists
- 🎯 **Assignment Viewing** - See who you're Secret Santa for
- ✅ **Purchase Tracking** - Mark items as purchased (only you can see)
- 💰 **Price Tracking** - Track estimated gift prices
- ⏰ **Countdown Timer** - Days remaining until the exchange
- 👫 **Couples Protection** - Algorithm ensures couples don't get each other
- 🎨 **Festive Theme** - Christmas-themed UI with snowflakes, gradients, and animations
- 💾 **Local Database** - Uses SQLite for easy setup (no external services required)

## Tech Stack

- **Frontend**: Next.js 15, React, TypeScript, Tailwind CSS
- **Backend**: SQLite (better-sqlite3)
- **Authentication**: Iron Session (encrypted cookies)
- **Package Manager**: npm (or Bun for faster performance)

## Prerequisites

- Node.js 18+ or Bun 1.0+ installed
- npm, yarn, or bun package manager

## Quick Start

### 1. Install Dependencies

**Using npm:**
```bash
npm install
```

**Using Bun (faster):**
```bash
bun install
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Edit `.env.local`:

```env
# Session Configuration - IMPORTANT: Change this to a secure random string!
SESSION_SECRET=your_super_secret_session_key_at_least_32_chars

# Secret Santa Configuration
NEXT_PUBLIC_SECRET_SANTA_DATE=2025-12-25
```

**Important**: Generate a secure session secret for production! You can use:
```bash
openssl rand -base64 32
```

### 3. Configure Participants

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

### 4. Create Users (Seed Database)

Run the seed script to create user accounts:

```bash
npm run seed
```

This will:
- Create the SQLite database (`secret-santa.db`)
- Create user accounts for all participants
- Set default password: `secretsanta123`

**Note**: In production, you should change the default passwords!

### 5. Generate Secret Santa Assignments

Start the dev server:

```bash
npm run dev
```

Then visit `http://localhost:3000/admin` and click "Generate Assignments".

Alternatively, use curl:
```bash
curl -X POST http://localhost:3000/api/admin/generate-assignments
```

### 6. Test It Out

1. Go to `http://localhost:3000/login`
2. Login with any participant email and password: `secretsanta123`
3. See the festive dashboard!

## Running the Application

**Using npm:**
```bash
# Development
npm run dev

# Production build
npm run build
npm start

# Seed database
npm run seed
```

**Using Bun:**
```bash
# Development
bun run dev

# Production build
bun run build
bun start

# Seed database
bun run seed
```

Open [http://localhost:3000](http://localhost:3000) to access the application.

## Usage

### For Participants

1. **Login**: Navigate to `/login` and enter your email and password
2. **View Assignment**: See who you're Secret Santa for on the dashboard
3. **View Their Wishlist**: Browse your target's wishlist with prices and links
4. **Mark as Purchased**: Track which items you've bought (only you see this)
5. **Manage Your Wishlist**: Switch to "My Wishlist" tab to add/edit items
6. **Add Items**: Include title, description, price, and product URLs

### For Administrators

**Access Admin Panel**: Visit `/admin`

**Generate New Assignments**:
```bash
curl -X POST http://localhost:3000/api/admin/generate-assignments
```

**Send Notifications** (stubbed - logs to console):
```bash
curl -X POST http://localhost:3000/api/admin/send-notifications
```

**Seed Users**:
```bash
npm run seed
```

**Important**: In production, protect the admin endpoints with authentication.

## File Structure

```
secret-santa/
├── app/
│   ├── api/
│   │   ├── admin/             # Admin API routes
│   │   ├── auth/              # Authentication routes (login/logout)
│   │   └── wishlist/          # Wishlist CRUD operations
│   ├── dashboard/             # Main user dashboard
│   ├── login/                 # Festive login page
│   ├── admin/                 # Admin panel
│   └── layout.tsx             # Root layout
├── components/
│   ├── ChristmasBackground.tsx # Snowfall & lights animation
│   ├── WishlistEditor.tsx     # Edit your own wishlist
│   └── TargetWishlist.tsx     # View target's wishlist
├── lib/
│   ├── db/                    # SQLite database setup and queries
│   │   ├── index.ts           # Database initialization
│   │   └── queries.ts         # Database query functions
│   ├── participants.ts        # Participant configuration (EDIT THIS!)
│   ├── secret-santa-algorithm.ts
│   ├── session.ts             # Session management
│   ├── email.ts               # Email functions (stubbed)
│   └── types.ts               # TypeScript type definitions
├── scripts/
│   └── seed.ts                # Database seeding script
├── secret-santa.db            # SQLite database (auto-created, gitignored)
├── .env.local                 # Environment variables (create this)
└── README.md                  # This file
```

## Database

The application uses SQLite for easy setup:

- **Database File**: `secret-santa.db` (created automatically in project root)
- **Tables**:
  - `users` - User accounts with hashed passwords
  - `assignments` - Secret Santa assignments (who gives to whom)
  - `wishlist_items` - Wishlist items with prices and URLs

The database schema is automatically created when the application starts.

### Database Management

- **Reset Database**: Delete `secret-santa.db` and run `npm run seed`
- **View Database**: Use any SQLite browser (e.g., DB Browser for SQLite)
- **Backup**: Copy the `secret-santa.db` file

## Security Considerations

- Passwords are hashed using bcrypt
- Sessions are encrypted using iron-session
- Users can only see their own profile and wishlist
- Users can only see the wishlist of their assigned person
- Assignment data is protected - users only see who they give to
- Admin endpoints should be protected in production
- **Change the default password** after seeding!

## Troubleshooting

**"Invalid email or password" error**:
- Verify user was created (check `npm run seed` output)
- Default password is: `secretsanta123`

**"No assignment found"**:
- Run generate-assignments from admin panel or API
- Ensure users exist for all participants in `lib/participants.ts`

**Database errors**:
- Delete `secret-santa.db` and run `npm run seed` again
- Check that better-sqlite3 installed correctly

**Couples getting each other**:
- Verify couples are correctly defined in `lib/participants.ts`
- Re-run assignment generation

**Session issues**:
- Clear browser cookies
- Ensure `SESSION_SECRET` is set in `.env.local`

## Customization

### Change Event Date

Edit `.env.local`:
```env
NEXT_PUBLIC_SECRET_SANTA_DATE=2025-12-31
```

### Change Default Password

Edit `scripts/seed.ts`:
```typescript
const DEFAULT_PASSWORD = 'your_new_password'
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
