import java.util.Base64
import java.security.KeyStore
import java.security.MessageDigest
import java.net.URI

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// flutterfire configure supplies this ignored file for the real application ID.
// Analysis/tests and unconfigured local builds must not require a Firebase project.
if (file("src/development/google-services.json").exists() || file("src/staging/google-services.json").exists() || file("src/production/google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}

android {
    namespace = "com.agapay.agapay_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.agapay.agapay_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = 24
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    flavorDimensions += "environment"
    productFlavors {
        create("development") { dimension = "environment"; applicationIdSuffix = ".development"; versionNameSuffix = "-dev" }
        create("staging") { dimension = "environment"; applicationIdSuffix = ".staging"; versionNameSuffix = "-staging" }
        create("production") { dimension = "environment" }
    }
    signingConfigs {
        create("protectedRelease") {
            System.getenv("AGAPAY_KEYSTORE_PATH")?.takeIf { it.isNotBlank() }?.let { storeFile = file(it) }
            storePassword = System.getenv("AGAPAY_KEYSTORE_PASSWORD")
            keyAlias = System.getenv("AGAPAY_KEY_ALIAS")
            keyPassword = System.getenv("AGAPAY_KEY_PASSWORD")
        }
    }
    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("protectedRelease")
            isMinifyEnabled = true
            isShrinkResources = true
            ndk { debugSymbolLevel = "FULL" }
        }
    }
}

flutter {
    source = "../.."
}

// Only development debug/profile and protected staging/production releases exist.
androidComponents {
    beforeVariants { variant ->
        val flavor = variant.productFlavors.firstOrNull { it.first == "environment" }?.second
        if ((flavor == "development" && variant.buildType == "release") ||
            (flavor != "development" && variant.buildType != "release")) variant.enable = false
    }
}

fun requirePublicHttps(value: String) {
    val uri = URI(value)
    val host = uri.host?.lowercase() ?: ""
    require(uri.scheme == "https" && host.contains('.') && !host.contains(':') && !host.matches(Regex("^[0-9].*")) &&
        host != "localhost" && !host.endsWith(".local") && !host.endsWith(".localhost") &&
        uri.userInfo == null && uri.query == null && uri.fragment == null && uri.path in listOf("", "/")) {
        "Protected builds require a reviewed public HTTPS origin"
    }
}
for (flavor in listOf("staging", "production")) {
    val capitalized = flavor.replaceFirstChar { it.uppercase() }
    val validation = tasks.register("validate${capitalized}ReleasePolicy") {
        doLast {
            val required = listOf("AGAPAY_KEYSTORE_PATH", "AGAPAY_KEYSTORE_PASSWORD", "AGAPAY_KEY_ALIAS", "AGAPAY_KEY_PASSWORD", "AGAPAY_UPLOAD_SIGNER_SHA256")
            require(required.all { !System.getenv(it).isNullOrBlank() }) { "Protected signing environment is incomplete; no debug fallback exists" }
            val signing = android.signingConfigs.getByName("protectedRelease")
            val store = KeyStore.getInstance(KeyStore.getDefaultType())
            signing.storeFile!!.inputStream().use { store.load(it, signing.storePassword!!.toCharArray()) }
            val certificate = store.getCertificate(signing.keyAlias) ?: error("Configured signer certificate is missing")
            val fingerprint = MessageDigest.getInstance("SHA-256").digest(certificate.encoded).joinToString("") { "%02x".format(it) }
            require(fingerprint.equals(System.getenv("AGAPAY_UPLOAD_SIGNER_SHA256").replace(":", ""), true)) { "Upload signer fingerprint does not match protected release identity" }
            require(!certificate.toString().contains("Android Debug", true) && signing.keyAlias != "androiddebugkey") { "Android debug signer is forbidden for protected releases" }
            val defines = (project.findProperty("dart-defines") as? String ?: "").split(',').filter { it.isNotBlank() }.associate {
                val pair = String(Base64.getDecoder().decode(it)).split('=', limit=2)
                pair[0] to pair.getOrElse(1) { "" }
            }
            require(defines["AGAPAY_ENV"] == flavor) { "Native/Dart environment mismatch" }
            requirePublicHttps(defines["AGAPAY_API_URL"] ?: "")
            require((defines["AGAPAY_REVISION"] ?: "").matches(Regex("[a-f0-9]{40}"))) { "Full source revision required" }
            require((defines["AGAPAY_RELEASE_ID"] ?: "").matches(Regex("[A-Za-z0-9._-]{3,100}"))) { "Immutable release identity required" }
            require((project.findProperty("dart-obfuscation") as? String) == "true" && !(project.findProperty("split-debug-info") as? String).isNullOrBlank()) { "Archive split Dart symbols for every protected build" }
            require(flutter.versionCode > 0 && flutter.versionName.matches(Regex("[0-9]+\\.[0-9]+\\.[0-9]+"))) { "Explicit semantic version and positive build number required" }
            val mode = defines["AGAPAY_MAP_MODE"] ?: "list_only"
            require(mode in listOf("list_only", "hosted")) { "Unknown protected map profile" }
            if (mode == "hosted") {
                requirePublicHttps(defines["AGAPAY_MAP_ORIGIN"] ?: "")
                require((defines["AGAPAY_MAP_RESTRICTION_EVIDENCE_SHA256"] ?: "").matches(Regex("[a-f0-9]{64}"))) { "Retained Maps restriction review required" }
            }
            require(file("src/$flavor/google-services.json").isFile) { "Flavor-specific Firebase configuration required; generic development configuration cannot activate release push" }
        }
    }
    tasks.configureEach { if (name == "pre${capitalized}ReleaseBuild") dependsOn(validation) }
}
