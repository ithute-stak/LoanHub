import 'package:flutter/material.dart';

abstract final class LoanHubBreakpoints {
  static const compact = 360.0;
  static const stackedToolbar = 430.0;
  static const tablet = 720.0;
  static const wideTablet = 960.0;

  static bool isCompact(double width) => width < compact;
  static bool stackToolbar(double width) => width < stackedToolbar;
  static bool useNavigationRail(double width) => width >= tablet;

  static double pagePadding(double width) {
    if (width < compact) return 12;
    if (width < 600) return 16;
    if (width < wideTablet) return 24;
    return 32;
  }

  static int dashboardColumns(double width) {
    if (width < 390) return 1;
    if (width < tablet) return 2;
    if (width < 1040) return 3;
    return 4;
  }

  static double dashboardAspectRatio(double width) {
    final columns = dashboardColumns(width);
    if (columns == 1) return 2.5;
    if (columns == 2) return 1.45;
    return 1.35;
  }
}

class LoanHubResponsiveCenter extends StatelessWidget {
  const LoanHubResponsiveCenter({
    required this.child,
    this.maxWidth = 920,
    this.includeVerticalPadding = false,
    super.key,
  });

  final Widget child;
  final double maxWidth;
  final bool includeVerticalPadding;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final padding = LoanHubBreakpoints.pagePadding(constraints.maxWidth);
        return Center(
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth),
            child: Padding(
              padding: EdgeInsets.symmetric(
                horizontal: padding,
                vertical: includeVerticalPadding ? padding : 0,
              ),
              child: child,
            ),
          ),
        );
      },
    );
  }
}

class LoanHubScrollableViewport extends StatelessWidget {
  const LoanHubScrollableViewport({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final padding = LoanHubBreakpoints.pagePadding(constraints.maxWidth);
        return SingleChildScrollView(
          padding: EdgeInsets.all(padding),
          child: ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: constraints.maxHeight - (padding * 2),
            ),
            child: IntrinsicHeight(child: child),
          ),
        );
      },
    );
  }
}
