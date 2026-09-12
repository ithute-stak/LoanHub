package ls.ithute.loanhub

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.RingtoneManager
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    companion object {
        private const val CHANNEL = "ls.ithute.loanhub/notifications"
        private const val NOTIFICATION_PERMISSION_REQUEST = 7101
        private const val EXTRA_ROUTE = "loanhub_notification_route"
    }

    private var notificationBridge: MethodChannel? = null
    private var pendingInitialRoute: String? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        createNotificationChannels()
        pendingInitialRoute = intent?.getStringExtra(EXTRA_ROUTE)
        notificationBridge = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            CHANNEL,
        ).also { channel ->
            channel.setMethodCallHandler { call, result ->
                when (call.method) {
                    "createChannels" -> {
                        createNotificationChannels()
                        result.success(null)
                    }
                    "requestPermission" -> {
                        requestNotificationPermission()
                        result.success(null)
                    }
                    "showNotification" -> {
                        showLoanHubNotification(
                            eventId = call.argument<String>("eventId").orEmpty(),
                            title = call.argument<String>("title") ?: "LoanHub",
                            body = call.argument<String>("body") ?: "New LoanHub update",
                            category = call.argument<String>("category") ?: "events",
                            route = call.argument<String>("route").orEmpty(),
                        )
                        result.success(null)
                    }
                    "initialRoute" -> {
                        val route = pendingInitialRoute
                        pendingInitialRoute = null
                        result.success(route)
                    }
                    else -> result.notImplemented()
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val route = intent.getStringExtra(EXTRA_ROUTE).orEmpty()
        if (route.isNotEmpty()) {
            notificationBridge?.invokeMethod("notificationTap", route)
        }
    }

    private fun requestNotificationPermission() {
        if (
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(
                arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                NOTIFICATION_PERMISSION_REQUEST,
            )
        }
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val defaultSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        val channels = listOf(
            NotificationChannel(
                "loanhub_messages",
                "LoanHub Messages",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "New LoanHub chat messages"
                enableVibration(true)
                setSound(defaultSound, null)
            },
            NotificationChannel(
                "loanhub_money",
                "LoanHub Money",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Provider-confirmed incoming money and payment updates"
                enableVibration(true)
                setSound(defaultSound, null)
            },
            NotificationChannel(
                "loanhub_calls",
                "LoanHub Calls",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "LoanHub call events"
                enableVibration(true)
                setSound(defaultSound, null)
            },
            NotificationChannel(
                "loanhub_events",
                "LoanHub Updates",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "Other LoanHub realtime events"
                enableVibration(true)
                setSound(defaultSound, null)
            },
        )
        channels.forEach(manager::createNotificationChannel)
    }

    private fun showLoanHubNotification(
        eventId: String,
        title: String,
        body: String,
        category: String,
        route: String,
    ) {
        if (
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return

        val channelId = when (category.lowercase()) {
            "chat", "message" -> "loanhub_messages"
            "money", "payment" -> "loanhub_money"
            "call" -> "loanhub_calls"
            else -> "loanhub_events"
        }
        val launchIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra(EXTRA_ROUTE, route)
        }
        val requestCode = eventId.hashCode()
        val pendingIntent = PendingIntent.getActivity(
            this,
            requestCode,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, channelId)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        builder
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(Notification.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION))
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            @Suppress("DEPRECATION")
            builder.setPriority(Notification.PRIORITY_HIGH)
        }
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(requestCode, builder.build())
    }
}
