/**
 * Email functionality (STUBBED)
 *
 * This module contains stubbed email functions.
 * Replace these with actual email sending logic when ready.
 */

export interface EmailParams {
  to: string
  subject: string
  html: string
  text?: string
}

/**
 * Sends an email (STUBBED - logs to console instead)
 */
export async function sendEmail(params: EmailParams): Promise<boolean> {
  // Only log that an email was sent, NOT the content (to protect assignment privacy)
  console.log(`📧 [EMAIL STUB] Email sent to: ${params.to}`)
  console.log(`   Subject: ${params.subject}`)
  console.log('---')

  // Simulate successful send
  return true
}

/**
 * Sends Secret Santa assignment notification email
 */
export async function sendAssignmentEmail(
  recipientEmail: string,
  recipientName: string,
  assignedPersonName: string,
  password?: string
): Promise<boolean> {
  const subject = '🎅 Your Secret Santa Assignment!'

  const loginInfo = password
    ? `
    <p><strong>Your login credentials:</strong></p>
    <p>Email: ${recipientEmail}<br>
    Password: <code>${password}</code></p>
    <p>You can change your password after logging in.</p>
    `
    : ''

  const loginInfoText = password
    ? `
Your login credentials:
Email: ${recipientEmail}
Password: ${password}

You can change your password after logging in.
`
    : ''

  const html = `
    <h1>Ho Ho Ho! 🎅</h1>
    <p>Hi ${recipientName},</p>
    <p>You have been assigned to be the Secret Santa for:</p>
    <h2 style="color: #ff0000;">${assignedPersonName}</h2>
    ${loginInfo}
    <p>Log in to the Secret Santa app to see their wishlist and start shopping!</p>
    <p>Remember to keep it a secret! 🤫</p>
    <br>
    <p>Happy gifting!</p>
  `

  const text = `
    Hi ${recipientName},

    You have been assigned to be the Secret Santa for: ${assignedPersonName}
    ${loginInfoText}
    Log in to the Secret Santa app to see their wishlist and start shopping!

    Remember to keep it a secret!

    Happy gifting!
  `

  return sendEmail({
    to: recipientEmail,
    subject,
    html,
    text,
  })
}

/**
 * Sends welcome email to new users
 */
export async function sendWelcomeEmail(
  email: string,
  name: string
): Promise<boolean> {
  const subject = '🎄 Welcome to Secret Santa!'

  const html = `
    <h1>Welcome to Secret Santa! 🎄</h1>
    <p>Hi ${name},</p>
    <p>Your account has been created successfully!</p>
    <p>You can now:</p>
    <ul>
      <li>Create your wishlist</li>
      <li>View your Secret Santa assignment</li>
      <li>See your assigned person's wishlist</li>
    </ul>
    <p>Happy holidays!</p>
  `

  const text = `
    Welcome to Secret Santa!

    Hi ${name},

    Your account has been created successfully!

    You can now:
    - Create your wishlist
    - View your Secret Santa assignment
    - See your assigned person's wishlist

    Happy holidays!
  `

  return sendEmail({
    to: email,
    subject,
    html,
    text,
  })
}

/**
 * Sends reminder email about updating wishlist
 */
export async function sendWishlistReminderEmail(
  email: string,
  name: string,
  daysRemaining: number
): Promise<boolean> {
  const subject = `⏰ ${daysRemaining} days until Secret Santa!`

  const html = `
    <h1>Don't forget your wishlist! 🎁</h1>
    <p>Hi ${name},</p>
    <p>There are only <strong>${daysRemaining} days</strong> remaining until Secret Santa!</p>
    <p>Make sure your wishlist is up to date so your Secret Santa knows what to get you.</p>
    <p>Log in to update your wishlist now!</p>
  `

  const text = `
    Hi ${name},

    There are only ${daysRemaining} days remaining until Secret Santa!

    Make sure your wishlist is up to date so your Secret Santa knows what to get you.

    Log in to update your wishlist now!
  `

  return sendEmail({
    to: email,
    subject,
    html,
    text,
  })
}

/**
 * Sends notification to gifter that their recipient's wishlist is ready
 */
export async function sendWishlistReadyEmail(
  gifterEmail: string,
  gifterName: string,
  recipientName: string
): Promise<boolean> {
  const subject = `🎁 ${recipientName}'s Wishlist is Ready!`

  const html = `
    <h1>Great news! 🎄</h1>
    <p>Hi ${gifterName},</p>
    <p><strong>${recipientName}</strong> has finished updating their wishlist!</p>
    <p>Log in to the Secret Santa app to see what they're hoping for this year.</p>
    <p>Happy shopping! 🛍️</p>
  `

  const text = `
    Hi ${gifterName},

    Great news! ${recipientName} has finished updating their wishlist!

    Log in to the Secret Santa app to see what they're hoping for this year.

    Happy shopping!
  `

  return sendEmail({
    to: gifterEmail,
    subject,
    html,
    text,
  })
}
