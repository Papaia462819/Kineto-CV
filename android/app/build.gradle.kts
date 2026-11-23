plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "ro.kinetocv.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "ro.kinetocv.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
    }
    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    // MediaPipe citește modelul direct din APK, deci fișierul nu trebuie comprimat.
    androidResources {
        noCompress += "task"
    }
    // Modelul MediaPipe nu e în git: se copiază la build din ../models (același fișier ca în Python).
    sourceSets["main"].assets.srcDir(layout.buildDirectory.dir("generated/poseModel"))
}

val copyPoseModel by tasks.registering(Copy::class) {
    val model = rootProject.file("../models/pose_landmarker_full.task")
    doFirst {
        check(model.exists()) { "Lipseste ${model.path}: descarca modelul MediaPipe in folderul models/ (vezi README)" }
    }
    from(model)
    into(layout.buildDirectory.dir("generated/poseModel"))
}
tasks.named("preBuild") { dependsOn(copyPoseModel) }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.09.00")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.camera:camera-core:1.4.2")
    implementation("androidx.camera:camera-camera2:1.4.2")
    implementation("androidx.camera:camera-lifecycle:1.4.2")
    implementation("androidx.camera:camera-view:1.4.2")

    implementation("com.google.mediapipe:tasks-vision:0.10.29")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    testImplementation("junit:junit:4.13.2")
}
