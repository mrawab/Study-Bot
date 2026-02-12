plugins {
    id("com.android.application")
    id("kotlin-android")
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.study_bot_android_app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.study_bot_android_app"
        minSdk = flutter.minSdkVersion
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = "1.8"
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

dependencies {
    implementation("com.android.support:multidex:1.0.3")
    // <-- Correct Kotlin DSL syntax
    add("coreLibraryDesugaring", "com.android.tools:desugar_jdk_libs:2.1.5")
}

flutter {
    source = "../.."
}
