export interface Profile {
  id: string
  email: string
  full_name: string
  created_at: string
  updated_at: string
}

export interface Assignment {
  id: string
  giver_id: string
  receiver_id: string
  year: number
  created_at: string
}

export interface WishlistItem {
  id: string
  user_id: string
  title: string
  description: string | null
  price: number | null
  url: string | null
  is_purchased: boolean
  purchased_by: string | null
  created_at: string
  updated_at: string
}

export interface AssignmentWithReceiver extends Assignment {
  receiver: Profile
}

export interface WishlistItemWithPurchaser extends WishlistItem {
  purchaser?: Profile | null
}
