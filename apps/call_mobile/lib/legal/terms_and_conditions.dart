import 'package:flutter/material.dart';

import '../layout/loanhub_responsive.dart';
import '../widgets/loanhub_brand.dart';

class TermsConditionsPage extends StatelessWidget {
  const TermsConditionsPage({super.key});

  static const effectiveDate = '20 August 2026';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final pagePadding = LoanHubBreakpoints.pagePadding(
      MediaQuery.sizeOf(context).width,
    );
    return Scaffold(
      appBar: AppBar(title: const Text('Terms & Conditions')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 780),
            child: SelectionArea(
              child: ListView(
                padding: EdgeInsets.fromLTRB(pagePadding, 16, pagePadding, 36),
                children: [
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.primaryContainer,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            LoanHubAppIcon(size: 56, radius: 16),
                            SizedBox(width: 14),
                            Expanded(child: LoanHubHorizontalLogo(height: 38)),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'LoanHub Mobile Terms & Conditions',
                          style: theme.textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w900,
                            color: theme.colorScheme.onPrimaryContainer,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Effective date: $effectiveDate',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.colorScheme.onPrimaryContainer,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 22),
                  const Text(
                    'These Terms & Conditions govern use of the LoanHub mobile application. By signing in to or using the app, you agree to these terms and to the policies of the LoanHub company account through which you are authorized to work.',
                  ),
                  const _TermsSection(
                    number: '1',
                    title: 'Authorized business use',
                    body:
                        'LoanHub Mobile is intended for authorized employees, officers and approved users of organizations that use LoanHub. You may use the app only for legitimate work carried out for the company account to which you have been granted access. You must not use another person’s account or attempt to access a company, branch, client or feature that has not been assigned to you.',
                  ),
                  const _TermsSection(
                    number: '2',
                    title: 'Account and security responsibilities',
                    body:
                        'You are responsible for keeping your password, one-time codes, device and active LoanHub session secure. Do not share login credentials. You must promptly report a lost device, suspected account compromise or unauthorized access to your company administrator or LoanHub support so that access can be reviewed or revoked.',
                  ),
                  const _TermsSection(
                    number: '3',
                    title: 'Client and contact information',
                    body:
                        'The app may display client identity, telephone, loan and related company-authorized information. Where you choose the contact-sync feature, authorized LoanHub client names and telephone numbers may be written to the device contact book so that work calls can be identified. You must protect this information, use it only for approved business purposes and avoid copying, disclosing or exporting it without authority.',
                  ),
                  const _TermsSection(
                    number: '4',
                    title: 'Business calls and telecommunications',
                    body:
                        'LoanHub Mobile can initiate business calls through company-controlled internet, SIP, PBX or telecommunications services. Call quality, caller identification, inbound routing, transfers and availability can depend on the company’s network and telecommunications provider. The app must not be used for harassment, impersonation, unlawful collection activity, abusive communications or any purpose prohibited by your organization’s policies.',
                  ),
                  const _TermsSection(
                    number: '5',
                    title: 'Call recording and monitoring',
                    body:
                        'A company may enable call recording, quality review or authorized live monitoring within LoanHub. When those features are enabled, the app can show a recording-policy indicator and calls may be processed through the company-controlled media service. The company and its users are responsible for following all applicable notice, consent, employment, privacy and communications requirements before recording or monitoring calls.',
                  ),
                  const _TermsSection(
                    number: '6',
                    title: 'Call history, notes and work records',
                    body:
                        'Call status, duration, client or loan linkage, outcomes, notes and related business records may be stored in LoanHub. You must enter information accurately and professionally. Do not place passwords, payment-card secrets, unrelated private information or deliberately false information in call notes.',
                  ),
                  const _TermsSection(
                    number: '7',
                    title: 'Device permissions',
                    body:
                        'The app may request permissions such as microphone, contacts and Bluetooth access when required for calling, audio routing or optional contact synchronization. You can deny optional permissions, but some features may then be unavailable. LoanHub does not authorize users to bypass Android security controls or covertly intercept ordinary personal calls.',
                  ),
                  const _TermsSection(
                    number: '8',
                    title: 'Acceptable use',
                    body:
                        'You must not reverse engineer the service for harmful purposes, defeat access controls, interfere with other users, introduce malicious software, scrape client information, abuse telecommunications services, attempt unauthorized surveillance, or use LoanHub in a way that compromises clients, employees, companies or the platform.',
                  ),
                  const _TermsSection(
                    number: '9',
                    title: 'Privacy and retention',
                    body:
                        'Personal and business information processed through the app is handled according to LoanHub privacy notices and the relevant company’s configured policies. Recording retention, deletion, legal holds and access to quality-review material may be controlled by authorized company or platform roles. Your organization may also impose additional records-management requirements.',
                  ),
                  const _TermsSection(
                    number: '10',
                    title: 'Service availability and third parties',
                    body:
                        'LoanHub may depend on internet access, device services and third-party telecommunications or media providers. Temporary outages, maintenance, provider failures or network limitations may affect some features. Features that depend on external providers are available only when the required company integrations are active.',
                  ),
                  const _TermsSection(
                    number: '11',
                    title: 'Suspension and termination',
                    body:
                        'Access may be suspended, restricted or revoked when a user leaves an organization, changes role, violates these terms, creates a security risk, loses required authorization or when a company account is no longer entitled to the relevant service. Signing out does not remove business records that the company is required or permitted to retain.',
                  ),
                  const _TermsSection(
                    number: '12',
                    title: 'Changes to these terms',
                    body:
                        'LoanHub may update these terms as the application, security controls, integrations or business features change. The current version should be made available in the app. Continued use after an updated version takes effect means you accept the updated terms, subject to any additional acceptance process that may be required by your organization.',
                  ),
                  const _TermsSection(
                    number: '13',
                    title: 'Questions and support',
                    body:
                        'Questions about account access, company policy, client handling, recording rules or use of LoanHub should first be directed to your company administrator. Technical or platform questions may be escalated to the authorized LoanHub support channel used by your organization.',
                  ),
                  const SizedBox(height: 10),
                  Card(
                    child: Padding(
                      padding: EdgeInsets.all(16),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.info_outline_rounded),
                          SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'These app terms describe the operational rules for LoanHub Mobile. Organizations may apply additional employment, lending, collections, privacy, security or telecommunications policies to their users.',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TermsSection extends StatelessWidget {
  const _TermsSection({
    required this.number,
    required this.title,
    required this.body,
  });

  final String number;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$number. $title',
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          Text(body),
        ],
      ),
    );
  }
}
