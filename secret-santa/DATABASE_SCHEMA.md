# Secret Santa Database Schema

## Tables

### profiles
Extends Supabase auth.users with additional profile information.

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Enable Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Users can read their own profile
CREATE POLICY "Users can read own profile" ON profiles
  FOR SELECT USING (auth.uid() = id);

-- Users can update their own profile
CREATE POLICY "Users can update own profile" ON profiles
  FOR UPDATE USING (auth.uid() = id);
```

### assignments
Stores Secret Santa assignments (who gives to whom).

```sql
CREATE TABLE assignments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  giver_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  receiver_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  year INTEGER NOT NULL DEFAULT EXTRACT(YEAR FROM NOW()),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
  UNIQUE(giver_id, year),
  CHECK (giver_id != receiver_id)
);

-- Enable Row Level Security
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;

-- Users can only see their own assignment (who they are giving to)
CREATE POLICY "Users can read own assignment" ON assignments
  FOR SELECT USING (auth.uid() = giver_id);
```

### wishlist_items
Stores wishlist items for each user.

```sql
CREATE TABLE wishlist_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  price DECIMAL(10, 2),
  url TEXT,
  is_purchased BOOLEAN DEFAULT FALSE,
  purchased_by UUID REFERENCES profiles(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Enable Row Level Security
ALTER TABLE wishlist_items ENABLE ROW LEVEL SECURITY;

-- Users can read their own wishlist items
CREATE POLICY "Users can read own wishlist" ON wishlist_items
  FOR SELECT USING (auth.uid() = user_id);

-- Users can read wishlist items of people they are assigned to
CREATE POLICY "Users can read assigned person wishlist" ON wishlist_items
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM assignments
      WHERE assignments.giver_id = auth.uid()
      AND assignments.receiver_id = wishlist_items.user_id
    )
  );

-- Users can insert their own wishlist items
CREATE POLICY "Users can insert own wishlist items" ON wishlist_items
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can update their own wishlist items
CREATE POLICY "Users can update own wishlist items" ON wishlist_items
  FOR UPDATE USING (auth.uid() = user_id);

-- Users can delete their own wishlist items
CREATE POLICY "Users can delete own wishlist items" ON wishlist_items
  FOR DELETE USING (auth.uid() = user_id);

-- Givers can mark items as purchased
CREATE POLICY "Givers can mark items as purchased" ON wishlist_items
  FOR UPDATE USING (
    EXISTS (
      SELECT 1 FROM assignments
      WHERE assignments.giver_id = auth.uid()
      AND assignments.receiver_id = wishlist_items.user_id
    )
  )
  WITH CHECK (
    purchased_by = auth.uid() OR purchased_by IS NULL
  );
```

## Functions

### Handle new user creation
```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email)
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger for new user creation
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

### Update updated_at timestamp
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = TIMEZONE('utc'::text, NOW());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_wishlist_items_updated_at BEFORE UPDATE ON wishlist_items
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

## Setup Instructions

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Create a new query and paste the schema from above
4. Execute the queries in order
5. Verify that tables are created in the Table Editor
