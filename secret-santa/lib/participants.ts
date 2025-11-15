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
  { name: "Scott", email: "scotty.a.h@gmail.com" },
  { name: "Keslyn", email: "keslynhatlen@gmail.com" },
  { name: "Craig", email: "craig.hatlen@gmail.com" },
  { name: "Susan", email: "hats4fun@gmail.com" },
  { name: "Andrea", email: "a.hatlen@yahoo.com" },
  { name: "Jose", email: "jose.mps88@gmail.com" },
  { name: "Brad", email: "Brad_wilson_12@yahoo.com" },
  { name: "Dani", email: "hatlen.danielle@gmail.com" },
  { name: "Sue", email: "suejoetami@sbcglobal.net" },
]


/**
 * List of couples who should not be assigned to each other
 * Add or remove couples here
 */
export const couples: Couple[] = [
  { person1Email: "scotty.a.h@gmail.com", person2Email: "keslynhatlen@gmail.com" },
  { person1Email: "craig.hatlen@gmail.com", person2Email: "hats4fun@gmail.com" },
  { person1Email: "a.hatlen@yahoo.com", person2Email: "jose.mps88@gmail.com" },
  { person1Email: "Brad_wilson _12@yahoo.com", person2Email: "hatlen.danielle@gmail.com" },
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
