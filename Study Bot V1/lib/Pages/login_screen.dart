
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:study_bot_android_app/Pages/api_services.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _isLoading = false;
  bool _obscurePassword = true;
  bool _rememberMe = false;
  bool _autoChecking = true;
  final ApiClient _apiClient = ApiClient();

  @override
  void initState() {
    super.initState();
    _checkAutoLogin();
    _loadRememberedUsername();
  }

  Future<void> _checkAutoLogin() async {
    final prefs = await SharedPreferences.getInstance();
    
    // Check if user is guest
    final bool isGuest = prefs.getBool('is_guest') ?? false;
    if (isGuest) {
      if (mounted) {
        setState(() => _autoChecking = false);
        Navigator.pushReplacementNamed(context, '/home', arguments: 'Guest');
      }
      return;
    }
    
    // Check if user has saved credentials and "remember_me" is enabled
    final savedUsername = prefs.getString('username');
    final rememberMe = prefs.getBool('remember_me') ?? false;
    
    // Auto-login ONLY for remembered accounts (not guest)
    if (rememberMe && savedUsername != null && savedUsername.isNotEmpty) {
      // Verify with server that this user exists
      try {
        final response = await _apiClient.userService.fetchSettings(savedUsername);
        
        if (response.success && response.data != null && mounted) {
          setState(() => _autoChecking = false);
          Navigator.pushReplacementNamed(context, '/home', arguments: savedUsername);
          return;
        }
      } catch (e) {
        // If server check fails, show login screen
      }
    }
    
    if (mounted) {
      setState(() => _autoChecking = false);
    }
  }

  Future<void> _loadRememberedUsername() async {
    final prefs = await SharedPreferences.getInstance();
    final rememberMe = prefs.getBool('remember_me') ?? false;
    
    // Only load username if remember_me is enabled
    if (rememberMe && mounted) {
      final savedUsername = prefs.getString('username');
      if (savedUsername != null && savedUsername.isNotEmpty) {
        setState(() {
          _rememberMe = true;
          _usernameController.text = savedUsername;
        });
      }
    }
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  void _showSuccess(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.green,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  Future<void> _loginAsGuest() async {
    setState(() => _isLoading = true);

    try {
      final prefs = await SharedPreferences.getInstance();
      
      // Clear any previous login data
      await prefs.clear();
      
      // Set as guest
      await prefs.setBool('is_guest', true);
      await prefs.setBool('remember_me', false);
      
      if (!mounted) return;
      
      setState(() => _isLoading = false);
      Navigator.pushReplacementNamed(context, '/home', arguments: 'Guest');
      _showSuccess("Logged in as Guest");
      
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        _showError("Could not continue as guest");
      }
    }
  }

  Future<void> _login() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;

    if (username.isEmpty || password.isEmpty) {
      _showError("Username and password cannot be empty");
      return;
    }

    setState(() => _isLoading = true);

    try {
      // Use the mobile login endpoint that checks BOTH username and password
      final response = await _apiClient.authService.login(
        username: username.toLowerCase(),
        password: password,
      );

      if (response.success) {
        final prefs = await SharedPreferences.getInstance();
        
        // Real account login - mark as not guest
        await prefs.setBool('is_guest', false);
        
        // Save username for auto-login (if remember_me is checked)
        await prefs.setString('username', username.toLowerCase());
        
        // Save remember_me preference
        await prefs.setBool('remember_me', _rememberMe);

        if (!mounted) return;
        
        setState(() => _isLoading = false);
        Navigator.pushReplacementNamed(
          context,
          '/home',
          arguments: username.toLowerCase(),
        );
        
        _showSuccess("Login successful!");
        
      } else {
        if (mounted) {
          setState(() => _isLoading = false);
          
          // Check specific error messages
          final error = response.error?.toLowerCase() ?? '';
          if (error.contains('not found') || error.contains('invalid')) {
            _showError("Username or password is incorrect");
          } else {
            _showError(response.error ?? "Login failed");
          }
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        _showError("Network error. Please check your connection and try again.");
      }
    }
  }

  Future<void> _forgotPassword() async {
    final Uri url = Uri.parse('https://studybot.viewdns.net/forgot_password');
    if (!await launchUrl(url, mode: LaunchMode.externalApplication)) {
      _showError("Could not open password recovery page");
    }
  }

  Future<void> _createAccount() async {
    final Uri url = Uri.parse('https://studybot.viewdns.net/register');
    if (!await launchUrl(url, mode: LaunchMode.externalApplication)) {
      _showError("Could not open registration page");
    }
  }

  @override
  Widget build(BuildContext context) {
    // Show loading screen while checking auto-login
    if (_autoChecking) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 20),
              Text("Checking login status..."),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: Colors.grey[100],
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              child: Padding(
                padding: const EdgeInsets.only(top: 30, right: 20, left: 20),
                child: Column(
                  children: [
                    Column(
                      children: [
                        Image(
                          image: const AssetImage('assets/logo_tran.png'),
                          height: 200,
                        ).animate().fadeIn(
                          duration: const Duration(milliseconds: 500),
                        ),
                        const Text(
                          'Welcome Back',
                          style: TextStyle(
                            fontSize: 38,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 50),
                      ],
                    ),

                    // form
                    Padding(
                      padding: const EdgeInsets.all(10.0),
                      child: Column(
                        children: [
                          TextFormField(
                            style: const TextStyle(fontSize: 16),
                            cursorColor: const Color.fromARGB(255, 2, 85, 152),
                            controller: _usernameController,
                            decoration: const InputDecoration(
                              prefixIcon: Icon(
                                Icons.person,
                                color: Color.fromARGB(255, 2, 85, 152),
                              ),
                              labelText: 'Username',
                              border: OutlineInputBorder(
                                borderSide: BorderSide(
                                  color: Color.fromARGB(255, 2, 85, 152),
                                ),
                                borderRadius: BorderRadius.all(
                                  Radius.circular(15),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 32),
                          TextFormField(
                            controller: _passwordController,
                            obscureText: _obscurePassword,
                            enableSuggestions: false,
                            autocorrect: false,
                            decoration: InputDecoration(
                              prefixIcon: const Icon(
                                Icons.lock,
                                color: Color.fromARGB(255, 2, 85, 152),
                              ),
                              labelText: 'Password',
                              border: const OutlineInputBorder(
                                borderSide: BorderSide(color: Colors.grey),
                                borderRadius: BorderRadius.all(
                                  Radius.circular(15),
                                ),
                              ),
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _obscurePassword
                                      ? Icons.visibility
                                      : Icons.visibility_off,
                                ),
                                onPressed: () {
                                  setState(() {
                                    _obscurePassword = !_obscurePassword;
                                  });
                                },
                              ),
                            ),
                          ),
                          const SizedBox(height: 32),

                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Row(
                                children: [
                                  Checkbox(
                                    activeColor: const Color.fromARGB(
                                      255,
                                      2,
                                      85,
                                      152,
                                    ),
                                    value: _rememberMe,
                                    onChanged: (value) {
                                      setState(() {
                                        _rememberMe = value ?? false;
                                      });
                                    },
                                  ),
                                  const Text(
                                    'Remember Me',
                                    style: TextStyle(fontSize: 16),
                                  ),
                                ],
                              ),
                              TextButton(
                                onPressed: _forgotPassword,
                                child: const Text(
                                  'Forgot Password',
                                  style: TextStyle(
                                    fontSize: 16,
                                    color: Colors.black,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 30),

                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color.fromARGB(
                                  179,
                                  4,
                                  93,
                                  182,
                                ),
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 50,
                                  vertical: 15,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(10),
                                ),
                              ),
                              onPressed: _login,
                              child: const Text(
                                'Login',
                                style: TextStyle(
                                  fontSize: 18,
                                  color: Color.fromARGB(255, 255, 255, 255),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 32),

                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color.fromARGB(
                                  212,
                                  83,
                                  88,
                                  93,
                                ),
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 50,
                                  vertical: 15,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(15),
                                ),
                              ),
                              onPressed: _createAccount,
                              child: const Text(
                                'Create New Account',
                                style: TextStyle(
                                  fontSize: 18,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 10),
                    Padding(
                      padding: const EdgeInsets.only(right: 50, left: 50),
                      child: Divider(height: 30, color: Colors.grey[400]),
                    ),
                    const SizedBox(height: 10),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color.fromARGB(212, 83, 88, 93),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 50,
                          vertical: 15,
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(15),
                        ),
                      ),
                      onPressed: _loginAsGuest,
                      child: const Text(
                        'Login As Guest',
                        style: TextStyle(fontSize: 18, color: Colors.white),
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      '© 2026 Study Bot. All rights reserved.',
                      style: TextStyle(fontSize: 14, color: Colors.grey),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}