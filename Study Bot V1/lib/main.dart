import 'package:flutter/material.dart';
import 'package:study_bot_android_app/Pages/home_screen.dart';
import 'package:study_bot_android_app/Pages/lectures.dart';
import 'package:study_bot_android_app/Pages/login_screen.dart';
import 'package:study_bot_android_app/Pages/profile.dart';
import 'package:study_bot_android_app/Pages/splash_screen.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'dart:io';
import 'package:open_file/open_file.dart';

final FlutterLocalNotificationsPlugin flutterLocalNotificationsPlugin =
    FlutterLocalNotificationsPlugin();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize notifications with tap handler
  const AndroidInitializationSettings androidSettings =
      AndroidInitializationSettings('@mipmap/ic_launcher');

  final InitializationSettings settings = InitializationSettings(
    android: androidSettings,
  );

  // Handle notification tap - USE ONLY THIS APPROACH
  await flutterLocalNotificationsPlugin.initialize(
    settings: settings,
    onDidReceiveNotificationResponse: (NotificationResponse response) async {
      final payload = response.payload;
      if (payload != null && payload.isNotEmpty) {
        // Open the file when notification is tapped (foreground)
        try {
          await OpenFile.open(payload);
        } catch (e) {
          debugPrint("Error opening file: $e");
        }
      }
    },
    onDidReceiveBackgroundNotificationResponse:
        notificationTapBackground, // Reference the background handler
  );

  // Create notification channel
  await _createNotificationChannel();

  runApp(const MyApp());
}

Future<void> _createNotificationChannel() async {
  if (Platform.isAndroid) {
    const AndroidNotificationChannel channel = AndroidNotificationChannel(
      'download_channel',
      'Downloads',
      description: 'Downloaded lectures',
      importance: Importance.high,
      playSound: true,
      enableVibration: true,
    );

    await flutterLocalNotificationsPlugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.createNotificationChannel(channel);
  }
}

// Background notification handler - MUST be a top-level function
@pragma('vm:entry-point')
void notificationTapBackground(NotificationResponse response) {
  final payload = response.payload;
  if (payload != null && payload.isNotEmpty) {
    // Don't use async/await in background handler
    OpenFile.open(payload)
        .then((result) {
          debugPrint("File opened from background: $result");
        })
        .catchError((e) {
          debugPrint("Error opening file from background: $e");
        });
  }
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.light,
        primaryColor: const Color.fromARGB(255, 2, 85, 152),
        scaffoldBackgroundColor: Colors.white,
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.blue,
          foregroundColor: Colors.white,
        ),
      ),
      initialRoute: '/',
      routes: {
        '/': (context) => const SplashScreen(),
        '/login': (context) => const LoginScreen(),
        '/home': (context) => const HomeScreen(),
        '/profile': (context) => const Profile(),
        '/lectures': (context) => const Lectures(),
      },
    );
  }
}
