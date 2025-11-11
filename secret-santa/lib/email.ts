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
  console.log('📧 [EMAIL STUB] Would send email:')
  console.log('To:', params.to)
  console.log('Subject:', params.subject)
  console.log('Content:')
  console.log(params.text || params.html)
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
  assignedPersonName: string
): Promise<boolean> {
  const subject = '🎅 Your Secret Santa Assignment!'

  const html = `
    <h1>Ho Ho Ho! 🎅</h1>
    <p>Hi ${recipientName},</p>
    <p>You have been assigned to be the Secret Santa for:</p>
    <h2 style="color: #ff0000;">${assignedPersonName}</h2>
    <p>Log in to the Secret Santa app to see their wishlist and start shopping!</p>
    <p>Remember to keep it a secret! 🤫</p>
    <br>
    <p>Happy gifting!</p>
  `

  const text = `
    Hi ${recipientName},

    You have been assigned to be the Secret Santa for: ${assignedPersonName}

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
