import java.util.Properties

plugins {
    id("com.android.application")
    id("dev.flutter.flutter-gradle-plugin")
}

val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
val hasReleaseSigning = keystorePropertiesFile.exists()
val isCiBuild = System.getenv("CI")?.equals("true", ignoreCase = true) == true
val firebaseProjectId = System.getenv("LOANHUB_FIREBASE_PROJECT_ID").orEmpty()
val firebaseAppId = System.getenv("LOANHUB_FIREBASE_APP_ID").orEmpty()
val firebaseApiKey = System.getenv("LOANHUB_FIREBASE_API_KEY").orEmpty()
val firebaseMessagingSenderId = System.getenv("LOANHUB_FIREBASE_MESSAGING_SENDER_ID").orEmpty()
val firebaseConfigured = listOf(
    firebaseProjectId,
    firebaseAppId,
    firebaseApiKey,
    firebaseMessagingSenderId,
).all { it.isNotBlank() }
if (hasReleaseSigning) {
    keystorePropertiesFile.inputStream().use { keystoreProperties.load(it) }
}

android {
    namespace = "ls.ithute.loanhub"
    compileSdk = 37
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "ls.ithute.loanhub"
        minSdk = flutter.minSdkVersion
        targetSdk = 36
        versionCode = flutter.versionCode
        versionName = flutter.versionName

        // Flutter receives the same values through --dart-define. These native
        // resources let Firebase initialise before Dart when Android launches
        // the process to deliver a notification to a background/killed app.
        if (firebaseConfigured) {
            resValue("string", "google_app_id", firebaseAppId)
            resValue("string", "google_api_key", firebaseApiKey)
            resValue("string", "gcm_defaultSenderId", firebaseMessagingSenderId)
            resValue("string", "project_id", firebaseProjectId)
        }
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
            }
        }
    }

    buildTypes {
        release {
            when {
                hasReleaseSigning -> signingConfig = signingConfigs.getByName("release")
                isCiBuild -> signingConfig = signingConfigs.getByName("debug")
            }
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
