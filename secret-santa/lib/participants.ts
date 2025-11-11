/**
 * Secret Santa Participants Configuration
 *
 * Edit this file to add/remove participants and define couples.
 * Couples will not be assigned to each other in the Secret Santa draw.
 */

export interface Participant {
  name: string
  email: string
}

export interface Couple {
  person1Email: string
  person2Email: string
}

/**
 * List of all participants in the Secret Santa
 * Add or remove participants here
 */
export const participants: Participant[] = [
  { name: "Alice Johnson", email: "alice@example.com" },
  { name: "Bob Smith", email: "bob@example.com" },
  { name: "Carol Williams", email: "carol@example.com" },
  { name: "David Brown", email: "david@example.com" },
  { name: "Eve Davis", email: "eve@example.com" },
  { name: "Frank Miller", email: "frank@example.com" },
]

/**
 * List of couples who should not be assigned to each other
 * Add or remove couples here
 */
export const couples: Couple[] = [
  { person1Email: "alice@example.com", person2Email: "bob@example.com" },
  { person1Email: "carol@example.com", person2Email: "david@example.com" },
]

/**
 * Helper function to check if two people are a couple
 */
export function areCouples(email1: string, email2: string): boolean {
  return couples.some(
    (couple) =>
      (couple.person1Email === email1 && couple.person2Email === email2) ||
      (couple.person1Email === email2 && couple.person2Email === email1)
  )
}

/**
 * Get partner's email if person is in a couple
 */
export function getPartnerEmail(email: string): string | null {
  const couple = couples.find(
    (c) => c.person1Email === email || c.person2Email === email
  )

  if (!couple) return null

  return couple.person1Email === email ? couple.person2Email : couple.person1Email
}
