import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
// import 'package:study_bot_android_app/Pages/login_screen.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  Widget build(BuildContext context) {
    Size size = MediaQuery.of(context).size;
    return Scaffold(
      backgroundColor: Colors.white,
      body: Center(
        child: Image.asset('assets/logo_tran.png', width: size.width * 0.5)
            .animate(
              onComplete: (controller) =>
                  Navigator.pushReplacementNamed(context, '/login'),
            )
            .fadeIn(duration: Duration(milliseconds: 500))
            .fadeOut(
              delay: Duration(milliseconds: 1000),
              duration: Duration(milliseconds: 500),
            ),
      ),
    );
  }
}
