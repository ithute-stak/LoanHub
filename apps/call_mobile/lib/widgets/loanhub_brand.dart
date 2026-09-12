import 'package:flutter/material.dart';

const loanHubAppIconAsset = 'assets/branding/loanhub-app-icon.png';
const loanHubHorizontalLogoAsset =
    'assets/branding/loanhub-horizontal-logo.png';

class LoanHubAppIcon extends StatelessWidget {
  const LoanHubAppIcon({this.size = 92, this.radius = 24, super.key});

  final double size;
  final double radius;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      image: true,
      label: 'LoanHub logo',
      child: ClipRRect(
        borderRadius: BorderRadius.circular(radius),
        child: Image.asset(
          loanHubAppIconAsset,
          width: size,
          height: size,
          fit: BoxFit.cover,
          filterQuality: FilterQuality.high,
        ),
      ),
    );
  }
}

class LoanHubHorizontalLogo extends StatelessWidget {
  const LoanHubHorizontalLogo({
    this.height = 54,
    this.padding = const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
    this.backgroundColor,
    super.key,
  });

  final double height;
  final EdgeInsetsGeometry padding;
  final Color? backgroundColor;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      image: true,
      label: 'LoanHub',
      child: Container(
        padding: padding,
        decoration: BoxDecoration(
          color: backgroundColor,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Image.asset(
          loanHubHorizontalLogoAsset,
          height: height,
          fit: BoxFit.contain,
          filterQuality: FilterQuality.high,
        ),
      ),
    );
  }
}
