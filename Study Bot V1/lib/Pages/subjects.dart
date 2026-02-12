import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:study_bot_android_app/Pages/api_services.dart';

class Subjects extends StatefulWidget {
  const Subjects({super.key});

  @override
  State<Subjects> createState() => _SubjectsState();
}

class _SubjectsState extends State<Subjects> {
  List<Map<String, dynamic>> subjects = [];
  String? selectedSemester;
  String? selectedDepartment;
  bool isLoading = true;
  bool loadingSettings = true;
  String errorMessage = '';
  String username = '';
  bool isGuest = false;

  final ApiClient _apiClient = ApiClient();

  @override
  void initState() {
    super.initState();
    _loadUserInfo();
  }

  Future<void> _loadUserInfo() async {
    final prefs = await SharedPreferences.getInstance();

    // Get username and guest status
    setState(() {
      username = prefs.getString('username') ?? 'mobile_user';
      isGuest = prefs.getBool('is_guest') ?? true;
    });

    // Fetch user settings to get semester and department
    await _fetchUserSettings();
  }

  Future<void> _fetchUserSettings() async {
    setState(() => loadingSettings = true);

    try {
      // Fetch user settings from API using username
      final response = await _apiClient.userService.fetchSettings(username);

      if (response.success && response.data != null) {
        setState(() {
          selectedSemester = response.data!['semester'];
          selectedDepartment = response.data!['department'];

          // Check if user is guest from API response
          if (response.data!.containsKey('is_guest')) {
            isGuest = response.data!['is_guest'] ?? false;
          }

          loadingSettings = false;
        });

        // Now fetch subjects with the obtained semester and department
        if (selectedSemester != null && selectedDepartment != null) {
          await _fetchSubjects();
        } else {
          setState(() {
            isLoading = false;
            errorMessage = 'Please complete your settings first';
          });
        }
      } else {
        setState(() {
          loadingSettings = false;
          isLoading = false;
          errorMessage = 'Please complete your settings first';
        });
      }
    } catch (e) {
      setState(() {
        loadingSettings = false;
        isLoading = false;
        errorMessage = 'Failed to load user settings';
      });
    }
  }

  Future<void> _fetchSubjects() async {
    if (selectedSemester == null || selectedDepartment == null) {
      setState(() {
        isLoading = false;
        errorMessage = 'Semester and department are required';
      });
      return;
    }

    setState(() => isLoading = true);

    try {
      final response = await _apiClient.lectureService.fetchSubjects(
        semester: selectedSemester!,
        department: selectedDepartment!,
        userId: username,
      );

      if (response.success && response.data != null) {
        setState(() {
          subjects = response.data!;
          isLoading = false;
          errorMessage = '';
        });
      } else {
        setState(() {
          isLoading = false;
          errorMessage = response.error ?? 'Failed to load subjects';
        });
      }
    } catch (e) {
      setState(() {
        isLoading = false;
        errorMessage = 'Network error. Please try again.';
      });
    }
  }

  // void _showError(String message) {
  //   ScaffoldMessenger.of(context).showSnackBar(
  //     SnackBar(
  //       content: Text(message),
  //       backgroundColor: Colors.red,
  //       duration: const Duration(seconds: 3),
  //     ),
  //   );
  // }

  void _onSubjectTap(Map<String, dynamic> subject) {
    // Navigate to lectures page
    Navigator.pushNamed(
      context,
      '/lectures',
      arguments: {
        'semester': selectedSemester,
        'department': selectedDepartment,
        'subject': subject['name'],
        'username': username,
      },
    );
  }

  String _formatFileSize(dynamic sizeMb) {
    // Handle both int and double values
    double size;
    if (sizeMb is int) {
      size = sizeMb.toDouble();
    } else if (sizeMb is double) {
      size = sizeMb;
    } else {
      size = 0.0;
    }

    if (size < 1) {
      return '${(size * 1024).toStringAsFixed(0)} KB';
    }
    return '${size.toStringAsFixed(1)} MB';
  }

  Widget _buildSubjectTile(Map<String, dynamic> subject) {
    final subjectName = subject['name'] ?? 'Unknown Subject';
    final lectureCount = subject['lecture_count'] ?? 0;
    final totalSize = subject['total_size_mb'] ?? 0;
    final hasFiles = subject['has_files'] ?? true;

    return Card(
      color: Colors.white,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: Container(
          width: 50,
          height: 50,
          decoration: BoxDecoration(
            // ignore: deprecated_member_use
            color: const Color.fromARGB(255, 2, 85, 152).withOpacity(0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(
            Icons.menu_book,
            color: const Color.fromARGB(255, 2, 85, 152),
            size: 28,
          ),
        ),
        title: Text(
          subjectName,
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(Icons.library_books, size: 16, color: Colors.grey[600]),
                const SizedBox(width: 6),
                Text(
                  '$lectureCount ${lectureCount == 1 ? 'lecture' : 'lectures'}',
                  style: TextStyle(fontSize: 14, color: Colors.grey[600]),
                ),
                const SizedBox(width: 16),
                Icon(Icons.storage, size: 16, color: Colors.grey[600]),
                const SizedBox(width: 6),
                Text(
                  _formatFileSize(totalSize),
                  style: TextStyle(fontSize: 14, color: Colors.grey[600]),
                ),
              ],
            ),
          ],
        ),
        trailing: Icon(Icons.chevron_right, color: Colors.grey[400], size: 28),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 12,
        ),
        onTap: hasFiles ? () => _onSubjectTap(subject) : null,
        enabled: hasFiles,
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.menu_book, size: 80, color: Colors.grey[300]),
          const SizedBox(height: 20),
          Text(
            selectedDepartment != null
                ? 'No Subjects Found for ${selectedDepartment!}'
                : 'No Subjects Found',
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w500,
              color: Colors.grey,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            selectedSemester != null
                ? 'Semester: ${selectedSemester!}'
                : 'Please complete your settings',
            style: const TextStyle(fontSize: 16, color: Colors.grey),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: _fetchSubjects,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color.fromARGB(255, 2, 85, 152),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            child: const Text('Refresh', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 80, color: Colors.red[300]),
          const SizedBox(height: 20),
          Text(
            'Error Loading Subjects',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w500,
              color: Colors.red[400],
            ),
          ),
          const SizedBox(height: 10),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Text(
              errorMessage,
              style: const TextStyle(fontSize: 16, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: () {
              _loadUserInfo(); // Reload everything
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color.fromARGB(255, 2, 85, 152),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            child: const Text(
              'Try Again',
              style: TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSettingsPrompt() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.settings, size: 80, color: Colors.orange[300]),
          const SizedBox(height: 20),
          const Text(
            'Settings Required',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w500,
              color: Colors.orange,
            ),
          ),
          const SizedBox(height: 10),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 32),
            child: Text(
              'Please complete your semester and department settings\nbefore viewing subjects.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, color: Colors.grey),
            ),
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: () {
              Navigator.pushNamed(context, '/profile');
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color.fromARGB(255, 2, 85, 152),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            child: const Text(
              'Go to Profile Settings',
              style: TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingSettings() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 20),
          Text('Loading your settings...'),
        ],
      ),
    );
  }

  String get semesterNumber => selectedSemester == null
      ? "—"
      : RegExp(r'\d+').firstMatch(selectedSemester!)?.group(0) ?? "—";

  @override
  Widget build(BuildContext context) {
    // NO Scaffold here - just the content
    return Center(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Header with refresh button
          Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (selectedDepartment != null)
                      Text(
                        'Department: ${selectedDepartment!}',
                        style: TextStyle(fontSize: 18, color: Colors.black),
                      ),
                    if (selectedSemester != null) const SizedBox(height: 5),
                    Text(
                      'Semester: $semesterNumber',
                      style: TextStyle(fontSize: 18, color: Colors.black),
                    ),
                  ],
                ),
                IconButton(
                  onPressed: () {
                    _loadUserInfo(); // Refresh everything
                  },
                  icon: const Icon(Icons.refresh),
                  tooltip: 'Refresh',
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(left: 20.0, right: 20),
            child: Divider(height: 10, color: Colors.grey),
          ),
          // Content area
          Expanded(
            child: loadingSettings
                ? _buildLoadingSettings()
                : selectedSemester == null || selectedDepartment == null
                ? _buildSettingsPrompt()
                : isLoading
                ? const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        CircularProgressIndicator(),
                        SizedBox(height: 20),
                        Text('Loading subjects...'),
                      ],
                    ),
                  )
                : errorMessage.isNotEmpty
                ? _buildErrorState()
                : subjects.isEmpty
                ? _buildEmptyState()
                : RefreshIndicator(
                    onRefresh: () async {
                      await _fetchSubjects();
                    },
                    child: Column(
                      children: [
                        // Subject count
                        Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 20,
                          ),
                          child: Text(
                            '${subjects.length} ${subjects.length == 1 ? 'subject' : 'subjects'} found',
                            style: TextStyle(
                              fontSize: 16,
                              letterSpacing: 2,
                              color: Colors.grey[700],
                            ),
                          ),
                        ),
                        Expanded(
                          child: ListView.builder(
                            padding: const EdgeInsets.only(bottom: 20),
                            itemCount: subjects.length,
                            itemBuilder: (context, index) {
                              return _buildSubjectTile(subjects[index]);
                            },
                          ),
                        ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}
