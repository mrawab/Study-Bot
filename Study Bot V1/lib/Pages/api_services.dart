import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiConstants {
  static const String baseUrl = 'https://studybot.viewdns.net';
  // static const String baseUrl = 'http://192.168.1.19:5000'; // Development

  // Endpoints
  static const String login = '/api/mobile/login';
  static const String userLogin = '/api/user/login';
  static const String userRegister = '/api/user/register';
  static const String userUpdate = '/api/user/update';
  static const String userSettings = '/api/user/settings';
  static const String semesters = '/api/mobile/semesters';
  static const String departments = '/api/mobile/departments';
  static const String subjects = '/api/mobile/subjects';
  static const String lectures = '/api/mobile/lectures';
  static const String lectureInfo = '/api/mobile/lecture/info';
  static const String download = '/api/mobile/download';
  static const String health = '/api/mobile/health';

  // Timeouts
  static const Duration connectTimeout = Duration(seconds: 10);
  static const Duration receiveTimeout = Duration(seconds: 30);
}

class ApiResponse<T> {
  final bool success;
  final T? data;
  final String? error;
  final int? statusCode;

  ApiResponse({required this.success, this.data, this.error, this.statusCode});

  factory ApiResponse.success(T data, [int? statusCode]) =>
      ApiResponse(success: true, data: data, statusCode: statusCode);

  factory ApiResponse.error(String error, [int? statusCode]) =>
      ApiResponse(success: false, error: error, statusCode: statusCode);
}

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, [this.statusCode]);

  @override
  String toString() =>
      'ApiException: $message ${statusCode != null ? '($statusCode)' : ''}';
}

class ApiService {
  final String baseUrl;
  final Map<String, String> defaultHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  ApiService({String? customBaseUrl})
    : baseUrl = customBaseUrl ?? ApiConstants.baseUrl;

  Future<Map<String, dynamic>> _makeRequest(
    Uri url, {
    String method = 'GET',
    Map<String, dynamic>? body,
    Map<String, String>? headers,
  }) async {
    try {
      final requestHeaders = {...defaultHeaders, ...?headers};
      http.Response response;

      switch (method.toUpperCase()) {
        case 'POST':
          response = await http
              .post(
                url,
                headers: requestHeaders,
                body: body != null ? jsonEncode(body) : null,
              )
              .timeout(ApiConstants.receiveTimeout);
          break;
        case 'PUT':
          response = await http
              .put(
                url,
                headers: requestHeaders,
                body: body != null ? jsonEncode(body) : null,
              )
              .timeout(ApiConstants.receiveTimeout);
          break;
        case 'DELETE':
          response = await http
              .delete(
                url,
                headers: requestHeaders,
                body: body != null ? jsonEncode(body) : null,
              )
              .timeout(ApiConstants.receiveTimeout);
          break;
        default: // GET
          response = await http
              .get(url, headers: requestHeaders)
              .timeout(ApiConstants.receiveTimeout);
      }

      final responseData = jsonDecode(utf8.decode(response.bodyBytes));

      if (response.statusCode >= 200 && response.statusCode < 300) {
        return responseData;
      } else {
        throw ApiException(
          responseData['error'] ??
              'Request failed with status ${response.statusCode}',
          response.statusCode,
        );
      }
    } on http.ClientException catch (e) {
      throw ApiException('Network error: ${e.message}');
    } on FormatException catch (e) {
      throw ApiException('Invalid response format: ${e.message}');
    } catch (e) {
      throw ApiException('Unexpected error: ${e.toString()}');
    }
  }

  // Health check
  Future<bool> checkHealth() async {
    try {
      final response = await _makeRequest(
        Uri.parse('$baseUrl${ApiConstants.health}'),
      );
      return response['success'] == true;
    } catch (e) {
      return false;
    }
  }
}

class AuthService extends ApiService {
  Future<ApiResponse<Map<String, dynamic>>> login({
    required String username,
    required String password,
  }) async {
    try {
      if (username.isEmpty || password.isEmpty) {
        return ApiResponse.error('Username and password are required');
      }

      final data = await _makeRequest(
        Uri.parse('$baseUrl/api/mobile/login'),
        method: 'POST',
        body: {'username': username, 'password': password},
      );

      if (data['success'] == true) {
        return ApiResponse.success(data);
      } else {
        return ApiResponse.error(data['error'] ?? 'Login failed');
      }
    } on ApiException catch (e) {
      return ApiResponse.error(e.message);
    }
  }

  Future<ApiResponse<Map<String, dynamic>?>> getUser(String username) async {
    try {
      final data = await _makeRequest(
        Uri.parse('$baseUrl${ApiConstants.userLogin}'),
        method: 'POST',
        body: {'username': username},
      );

      return ApiResponse.success(data['settings']);
    } on ApiException catch (e) {
      return ApiResponse.error(e.message);
    }
  }
}

class UserService extends ApiService {
  Future<ApiResponse<bool>> register({
    required String name,
    required String semester,
    required String department,
    bool isGuest = false,
  }) async {
    try {
      final Map<String, dynamic> body = {
        'name': name.trim().toLowerCase(),
        'semester': semester,
        'department': department,
        'platform_is_mobile': true,
      };

      if (isGuest) {
        body['is_guest'] = true;
      }

      final data = await _makeRequest(
        Uri.parse('$baseUrl${ApiConstants.userRegister}'),
        method: 'POST',
        body: body,
      );

      return ApiResponse.success(data['success'] == true);
    } on ApiException catch (e) {
      return ApiResponse.error(e.message);
    }
  }

  Future<ApiResponse<bool>> updateUser({
    required String name,
    required String semester,
    required String department,
    String? oldName,
    bool upgrade = false,
  }) async {
    try {
      final Map<String, dynamic> body = {
        'name': name.trim().toLowerCase(),
        'semester': semester,
        'department': department,
      };

      if (upgrade && oldName != null) {
        body['old_name'] = oldName.trim().toLowerCase();
        body['upgrade'] = true;
      }

      final data = await _makeRequest(
        Uri.parse('$baseUrl${ApiConstants.userUpdate}'),
        method: 'POST',
        body: body,
      );

      return ApiResponse.success(data['success'] == true);
    } on ApiException catch (e) {
      return ApiResponse.error(e.message);
    }
  }

  Future<ApiResponse<Map<String, dynamic>?>> fetchSettings(
    String username,
  ) async {
    try {
      final data = await _makeRequest(
        Uri.parse(
          '$baseUrl${ApiConstants.userSettings}?username=${Uri.encodeComponent(username)}',
        ),
      );

      if (data['success'] == true) {
        return ApiResponse.success(data['settings']);
      }
      return ApiResponse.success(null);
    } on ApiException catch (e) {
      return ApiResponse.error(e.message);
    }
  }
}

class LectureService extends ApiService {
  Future<ApiResponse<List<String>>> fetchSemesters() async {
    try {
      final data = await _makeRequest(
        Uri.parse('$baseUrl${ApiConstants.semesters}'),
      );

      return ApiResponse.success(List<String>.from(data['semesters']));
    } on ApiException catch (e) {
      return ApiResponse.error(e.message);
    }
  }

  Future<ApiResponse<List<String>>> fetchDepartments(String semester) async {
    try {
      final data = await _makeRequest(
        Uri.parse(
          '$baseUrl${ApiConstants.departments}?semester=${Uri.encodeComponent(semester)}',
        ),
      );

      return ApiResponse.success(List<String>.from(data['departments']));
    } on ApiException catch (e) {
      return ApiResponse.error("Error from server ${e.message}");
    }
  }

  Future<ApiResponse<List<Map<String, dynamic>>>> fetchSubjects({
    required String semester,
    required String department,
    String userId = 'mobile_user',
  }) async {
    try {
      final params = {
        'semester': semester,
        'department': department,
        'user_id': userId,
      };

      final url = Uri.parse(
        '$baseUrl${ApiConstants.subjects}',
      ).replace(queryParameters: params);
      final data = await _makeRequest(url);

      return ApiResponse.success(
        List<Map<String, dynamic>>.from(data['subjects']),
      );
    } on ApiException catch (e) {
      return ApiResponse.error(e.message);
    }
  }

  Future<ApiResponse<List<Map<String, dynamic>>>> fetchLectures({
    required String semester,
    required String department,
    required String subject,
    String userId = 'mobile_user',
  }) async {
    try {
      final params = {
        'semester': semester,
        'department': department,
        'subject': subject,
        'user_id': userId,
      };

      final url = Uri.parse(
        '$baseUrl${ApiConstants.lectures}',
      ).replace(queryParameters: params);
      final data = await _makeRequest(url);

      return ApiResponse.success(
        List<Map<String, dynamic>>.from(data['lectures']),
      );
    } on ApiException catch (e) {
      return ApiResponse.error(e.message);
    }
  }

  Future<ApiResponse<Map<String, dynamic>>> getLectureInfo({
    required String semester,
    required String department,
    required String subject,
    required int lectureId,
  }) async {
    try {
      final params = {
        'semester': semester,
        'department': department,
        'subject': subject,
        'lecture_id': lectureId,
      };

      final url = Uri.parse(
        '$baseUrl${ApiConstants.lectureInfo}',
      ).replace(queryParameters: params);
      final data = await _makeRequest(url);

      return ApiResponse.success(data['lecture']);
    } on ApiException catch (e) {
      return ApiResponse.error(e.message);
    }
  }
}

// Usage example:
class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  final AuthService authService = AuthService();
  final UserService userService = UserService();
  final LectureService lectureService = LectureService();
  final ApiService apiService = ApiService();

  Future<bool> checkServerConnection() async {
    return await apiService.checkHealth();
  }
}
