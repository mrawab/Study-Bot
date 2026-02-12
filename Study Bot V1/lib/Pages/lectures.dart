import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:dio/dio.dart';
import 'package:study_bot_android_app/Pages/api_services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import '../main.dart';

class Lectures extends StatefulWidget {
  const Lectures({super.key});

  @override
  State<Lectures> createState() => _LecturesState();
}

class _LecturesState extends State<Lectures> {
  final ApiClient _apiClient = ApiClient();
  List<Map<String, dynamic>> lectures = [];
  bool isLoading = true;
  String errorMessage = '';

  String? semester;
  String? department;
  String? subject;
  String? username;

  double downloadProgress = 0.0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args =
        ModalRoute.of(context)!.settings.arguments as Map<String, dynamic>;
    semester = args['semester'];
    department = args['department'];
    subject = args['subject'];
    username = args['username'];

    _fetchLectures();
  }

  Future<bool> _requestStoragePermission() async {
    if (Platform.isAndroid) {
      if (await _isAndroid11OrAbove()) {
        final status = await Permission.manageExternalStorage.status;
        if (!status.isGranted) {
          final result = await Permission.manageExternalStorage.request();
          if (!result.isGranted) return false;
        }
      } else {
        var status = await Permission.storage.status;
        if (!status.isGranted) {
          status = await Permission.storage.request();
          if (!status.isGranted) return false;
        }
      }
    }
    return true;
  }

  Future<bool> _isAndroid11OrAbove() async {
    return Platform.isAndroid && (await _getSdkInt()) >= 30;
  }

  Future<int> _getSdkInt() async {
    try {
      if (!kIsWeb && Platform.isAndroid) {
        final result = await Process.run('getprop', ['ro.build.version.sdk']);
        return int.tryParse(result.stdout.toString()) ?? 30;
      }
    } catch (_) {}
    return 30;
  }

  void _showSnack(String msg, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: error ? Colors.red : Colors.green,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  Future<void> _downloadLecture(Map<String, dynamic> lecture) async {
    final lectureId = lecture['lecture_id'] ?? lecture['id'];
    final lectureName = lecture['title'] ?? 'Lecture_${lectureId ?? 0}.pdf';

    if (lectureId == null || username == null) return;

    if (Platform.isAndroid) {
      final status = await Permission.notification.status;
      if (!status.isGranted) {
        await Permission.notification.request();
      }
    }

    if (!(await _requestStoragePermission())) {
      _showSnack("Storage permission denied", error: true);
      return;
    }

    _showSnack("Downloading $lectureName");

    final uri = Uri.parse('https://studybot.viewdns.net/api/mobile/download')
        .replace(
          queryParameters: {
            'username': username!.trim(),
            'semester': semester!.trim(),
            'department': department!.trim(),
            'subject': subject!.trim(),
            'lecture_id': lectureId.toString(),
          },
        );

    Directory dir;
    if (Platform.isAndroid) {
      dir =
          await getExternalStorageDirectory() ??
          await getApplicationDocumentsDirectory();
    } else {
      dir = await getApplicationDocumentsDirectory();
    }

    if (!await dir.exists()) await dir.create(recursive: true);
    final savePath = "${dir.path}/$lectureName";

    final dio = Dio();
    final int notifId = DateTime.now().millisecondsSinceEpoch ~/ 1000;

    // Throttling variables
    DateTime lastUpdateTime = DateTime.now();
    const int minUpdateIntervalMs = 500; // Update at most every 500ms
    int lastProgress = -1;

    // Cancel any existing download progress
    CancelToken cancelToken = CancelToken();

    // Initial notification
    try {
      await flutterLocalNotificationsPlugin.show(
        id: notifId,
        title: "Downloading $lectureName",
        body: "0%",
        payload: savePath,
        notificationDetails: NotificationDetails(
          android: AndroidNotificationDetails(
            'download_channel',
            'Downloads',
            channelDescription: 'Downloaded lectures',
            importance: Importance.high,
            priority: Priority.high,
            onlyAlertOnce: true,
            showProgress: true,
            maxProgress: 100,
            progress: 0,
            ongoing: true,
            autoCancel: false,
            playSound: true,
            enableVibration: true,
            enableLights: true,
            category: AndroidNotificationCategory.progress,
            visibility: NotificationVisibility.public,
          ),
        ),
      );
    } catch (e) {
      debugPrint("Error showing initial notification: $e");
    }

    try {
      await dio.download(
        uri.toString(),
        savePath,
        cancelToken: cancelToken,
        onReceiveProgress: (received, total) async {
          if (total != -1 && mounted) {
            final progress = (received / total * 100).toInt();
            setState(() => downloadProgress = received / total);

            // Throttle notification updates - only update if:
            // 1. Progress changed significantly (at least 1%)
            // 2. It's been at least 500ms since last update
            // 3. It's 0% or 100% (force update)
            final now = DateTime.now();
            final timeSinceLastUpdate = now
                .difference(lastUpdateTime)
                .inMilliseconds;
            final shouldUpdate =
                progress != lastProgress &&
                (timeSinceLastUpdate >= minUpdateIntervalMs ||
                    progress == 0 ||
                    progress == 100);

            if (shouldUpdate) {
              lastUpdateTime = now;
              lastProgress = progress;

              try {
                await flutterLocalNotificationsPlugin.show(
                  id: notifId,
                  title: "Downloading $lectureName",
                  body: "$progress%",
                  payload: savePath,
                  notificationDetails: NotificationDetails(
                    android: AndroidNotificationDetails(
                      'download_channel',
                      'Downloads',
                      channelDescription: 'Downloaded lectures',
                      importance: Importance.high,
                      priority: Priority.high,
                      onlyAlertOnce: true,
                      showProgress: true,
                      maxProgress: 100,
                      progress: progress,
                      ongoing: true,
                      autoCancel: false,
                      playSound: false,
                      enableLights: false,
                      category: AndroidNotificationCategory.progress,
                      visibility: NotificationVisibility.public,
                    ),
                  ),
                );
              } catch (e) {
                debugPrint("Error updating notification: $e");
              }
            }
          }
        },
      );

      if (!mounted) return;
      setState(() => downloadProgress = 0.0);

      // Cancel any pending notification updates
      lastProgress = -1;

      // Final completed notification
      try {
        await flutterLocalNotificationsPlugin.show(
          id: notifId,
          title: "✅ Download Complete",
          body: "Tap to open: $lectureName",
          payload: savePath,
          notificationDetails: NotificationDetails(
            android: AndroidNotificationDetails(
              'download_channel',
              'Downloads',
              channelDescription: 'Downloaded lectures',
              importance: Importance.high,
              priority: Priority.high,
              ongoing: false,
              autoCancel: true,
              playSound: true,
              enableVibration: true,
              enableLights: true,
              category: AndroidNotificationCategory.status,
              visibility: NotificationVisibility.public,
              styleInformation: BigTextStyleInformation(
                "Tap to open the downloaded file",
                contentTitle: lectureName,
                summaryText: "Download complete",
              ),
            ),
          ),
        );
      } catch (e) {
        debugPrint("Error showing completion notification: $e");
      }

      _showSnack("Downloaded $lectureName");
    } catch (e) {
      if (!mounted) return;
      setState(() => downloadProgress = 0.0);
      lastProgress = -1;

      // Don't show error if cancelled
      if (e is DioException && CancelToken.isCancel(e)) {
        debugPrint("Download cancelled");
        return;
      }

      _showSnack("Failed to download $lectureName", error: true);

      // Show error notification
      try {
        await flutterLocalNotificationsPlugin.show(
          id: notifId,
          title: "❌ Download Failed",
          body: "Failed to download $lectureName",
          payload: null,
          notificationDetails: NotificationDetails(
            android: AndroidNotificationDetails(
              'download_channel',
              'Downloads',
              channelDescription: 'Downloaded lectures',
              importance: Importance.high,
              priority: Priority.high,
              ongoing: false,
              autoCancel: true,
              playSound: true,
              enableVibration: true,
              enableLights: true,
              category: AndroidNotificationCategory.status,
              visibility: NotificationVisibility.public,
            ),
          ),
        );
      } catch (notifError) {
        debugPrint("Error showing error notification: $notifError");
      }
    }
  }

  Future<void> _fetchLectures() async {
    if (semester == null ||
        department == null ||
        subject == null ||
        username == null) {
      if (mounted)
        setState(() {
          errorMessage = "Missing data";
          isLoading = false;
        });
      return;
    }

    if (mounted)
      setState(() {
        isLoading = true;
        errorMessage = '';
      });

    try {
      final response = await _apiClient.lectureService.fetchLectures(
        semester: semester!,
        department: department!,
        subject: subject!,
        userId: username!,
      );

      if (!mounted) return;

      if (response.success && response.data != null) {
        setState(() {
          lectures = response.data!;
          isLoading = false;
        });
      } else {
        setState(() {
          errorMessage = response.error ?? "Failed to load lectures";
          isLoading = false;
        });
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        errorMessage = "Network error";
        isLoading = false;
      });
    }
  }

  Widget _buildLectureTile(Map<String, dynamic> lecture) {
    final title = lecture['title'] ?? 'Untitled';
    final size = lecture['file_size_mb'] ?? 0;
    final num = lecture['lecture_number'] ?? '';
    return Card(
      color: Colors.white,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: const Icon(Icons.school, size: 30),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text("Lecture $num • $size MB"),
        trailing: const Icon(Icons.download),
        onTap: () => _downloadLecture(lecture),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(subject ?? "Lectures"),
        backgroundColor: const Color.fromARGB(255, 2, 85, 152),
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : errorMessage.isNotEmpty
          ? Center(
              child: Text(
                errorMessage,
                style: const TextStyle(color: Colors.red),
              ),
            )
          : lectures.isEmpty
          ? const Center(
              child: Text(
                "No lectures available",
                style: TextStyle(color: Colors.grey),
              ),
            )
          : RefreshIndicator(
              onRefresh: _fetchLectures,
              child: ListView.builder(
                padding: const EdgeInsets.only(top: 10),
                itemCount: lectures.length,
                itemBuilder: (context, index) =>
                    _buildLectureTile(lectures[index]),
              ),
            ),
    );
  }
}
