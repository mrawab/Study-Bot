import 'package:flutter/material.dart';

class Home extends StatelessWidget {
  const Home({super.key, required this.displayName, required this.isGuest});

  final String displayName;
  final bool isGuest;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Container(
        padding: EdgeInsets.all(10),
        child: Column(
          // mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Padding(
              padding: EdgeInsets.all(10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Welcome, $displayName',
                    style: const TextStyle(fontSize: 20),
                  ),
                  CircleAvatar(
                    radius: 20,
                    backgroundImage: const AssetImage('assets/user_avatar.png'),
                  ),
                ],
              ),
            ),
            Divider(height: 10, color: Colors.grey),
            Container(
              padding: EdgeInsets.only(top: 20, bottom: 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    "Find Us in:",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  SizedBox(height: 20),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        Image.asset("assets/user_avatar.png"),
                        SizedBox(width: 10),
                        Image.asset("assets/user_avatar.png"),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            Container(
              padding: EdgeInsets.only(top: 20, bottom: 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    "Our Top Features:",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  SizedBox(height: 20),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        Image.asset("assets/user_avatar.png"),
                        SizedBox(width: 10),
                        Image.asset("assets/user_avatar.png"),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            guestMessage(isGuest),
          ],
        ),
      ),
    );
  }
}

Widget guestMessage(bool isGuest) {
  return Column(
    children: [
      if (isGuest) ...[
        const SizedBox(height: 10),
        const Text(
          "Guest Account - Upgrade to save your progress",
          style: TextStyle(
            fontSize: 14,
            color: Colors.grey,
            fontStyle: FontStyle.italic,
          ),
        ),
      ],
    ],
  );
}
