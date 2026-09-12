import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "LoanHub Mobile Privacy Policy",
    description: "Privacy and data-use information for the LoanHub mobile application.",
};

const sections = [
    {
        title: "What this app is",
        body: [
            "LoanHub Mobile is a communications, lending-services and provider-backed payments application for LoanHub platform users, participating businesses, authorised staff, borrowers/clients and people interested in LoanHub services.",
            "The app can create a basic interested-client account. Creating an account or transfer instruction does not approve credit and does not by itself confirm that money has settled.",
        ],
    },
    {
        title: "Information processed by LoanHub Mobile",
        body: [
            "Account and organisation data: sign-in identifier, authentication tokens, user role, company/branch context where applicable, display name and device registration information.",
            "Client and lending data: authorised borrower/client identifiers, contact information, loan references and limited lending information that the signed-in user's LoanHub permissions allow them to access.",
            "Chat data: conversation membership, encrypted message content stored by LoanHub, message timestamps, read state, typing/presence events, and supported file or voice-message metadata.",
            "Money data: transfer type, amount, currency, payer/payee details or LoanHub references, provider transaction status, payment references and audit information. External settlement is final only after the configured payment provider confirms it.",
            "Call data: calling/called number, direction, start/answer/end times, duration, status, employee, client/loan association, transfer information, call outcome and authorised notes.",
            "Call audio: during a controlled LoanHub business call, microphone audio is transmitted to the configured real-time communications/telephony service. If an organisation's recording policy is enabled, that call may be recorded on the controlled media/PBX path according to policy and law.",
        ],
    },
    {
        title: "Realtime and notification data",
        body: [
            "While the app is open, LoanHub uses an authenticated WebSocket connection for permitted realtime events such as messages, typing/presence and payment updates.",
            "For background notifications, the app registers an app-generated device UUID and a push-notification token with LoanHub. A push delivery service may process that token and the minimum notification-routing information needed to deliver an alert.",
            "Notification content can include a message preview or a provider-confirmed incoming-money amount. Android notification settings allow the user to control notification permission, sound and vibration.",
            "When the app returns to the foreground it reconnects and refreshes authoritative LoanHub state. Android may prevent background delivery after a user force-stops the application.",
        ],
    },
    {
        title: "Contacts permission",
        body: [
            "Contact synchronisation is optional and starts only when an authorised user chooses to sync LoanHub client contacts.",
            "The app reads phone numbers already present on the device to avoid creating duplicates and writes authorised LoanHub client contacts into the device contact book. Personal phone-book contacts are not intentionally uploaded to LoanHub by the contact-sync feature.",
            "Contacts permission can be denied while continuing to use other available LoanHub functions.",
        ],
    },
    {
        title: "Microphone permission",
        body: [
            "Microphone access is used for controlled LoanHub calling when that feature is available to the signed-in role. It is not used to covertly record ordinary SIM calls.",
            "Audio may be processed by the configured media or telecommunications provider to provide calling, recording, transfer, conferencing and related telephony functions where enabled.",
        ],
    },
    {
        title: "Notification permission",
        body: [
            "On supported Android versions LoanHub requests notification permission so it can alert the user to new messages, provider-confirmed incoming money, calls and important LoanHub events.",
            "Users can disable or change LoanHub notification sounds, vibration and visibility through Android settings. Disabling notifications does not prevent the user from opening the app and refreshing current data.",
        ],
    },
    {
        title: "How information is used",
        body: [
            "Information is used to authenticate and authorise users, provide chat and support, show permitted lending information, process and reconcile provider-backed payment instructions, provide controlled business calling, maintain required business records, deliver realtime notifications, protect accounts and support audit/compliance functions.",
            "LoanHub does not sell personal information obtained through the mobile app.",
        ],
    },
    {
        title: "Storage, security and retention",
        body: [
            "Authentication tokens are stored using platform secure-storage facilities. Limited pending metadata can be stored locally for retry/recovery when connectivity is unavailable.",
            "Production LoanHub connections must use encrypted HTTPS/WSS transport. Provider-side voice and payment security depend on the configured production service and its verified controls.",
            "Chat, payment, call, recording and audit data are retained according to LoanHub/company policies, contractual requirements, legal holds and applicable law. Push-device registrations are deactivated when revoked or signed out where connectivity permits.",
        ],
    },
    {
        title: "Access, correction and deletion requests",
        body: [
            "Borrowers and interested users may have personal LoanHub accounts, while company users can also have organisation-managed access. Requests to access, correct, export or delete information should be directed through the applicable LoanHub privacy/support process or organisation administrator, depending on who controls the record.",
            "For application-level privacy enquiries, use the developer contact published with LoanHub in Google Play. Account-deletion availability and any required verification depend on the account and records that must be retained for legitimate legal, financial, audit or contractual purposes.",
        ],
    },
    {
        title: "Children",
        body: [
            "LoanHub is a financial-services/business application and is not designed or directed to children.",
        ],
    },
    {
        title: "Changes to this policy",
        body: [
            "This policy may be updated when the application, payment or telecommunications integrations, data handling practices or legal requirements change. The current version will remain available at this public page.",
        ],
    },
];

export default function LoanHubMobilePrivacyPage() {
    return (
        <main className="min-h-screen bg-slate-50 px-5 py-10 text-slate-900 sm:px-8">
            <article className="mx-auto max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-10">
                <header className="border-b border-slate-200 pb-6">
                    <p className="text-sm font-bold uppercase tracking-[0.18em] text-emerald-700">LoanHub</p>
                    <h1 className="mt-2 text-3xl font-black tracking-tight">Mobile Privacy Policy</h1>
                    <p className="mt-3 text-sm text-slate-500">Last updated: 20 August 2026</p>
                    <p className="mt-4 leading-7 text-slate-700">
                        This policy explains how the LoanHub mobile app processes data, uses device permissions and delivers realtime/background notifications.
                    </p>
                </header>

                <div className="space-y-8 pt-8">
                    {sections.map((section) => (
                        <section key={section.title}>
                            <h2 className="text-xl font-extrabold">{section.title}</h2>
                            <div className="mt-3 space-y-3 text-sm leading-7 text-slate-700">
                                {section.body.map((paragraph) => (
                                    <p key={paragraph}>{paragraph}</p>
                                ))}
                            </div>
                        </section>
                    ))}
                </div>
            </article>
        </main>
    );
}
