package com.ramil.myplayer

import android.Manifest
import android.content.ContentUris
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import kotlinx.coroutines.delay

data class Track(val id: Long, val name: String, val uri: Uri)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val opened = intent?.data
        setContent { PlayerApp(opened) }
    }
}

private val Green = Color(0xFF3DD68C)
private val Bg = Color(0xFF0B1210)
private val Card = Color(0xFF16201C)

@Composable
fun PlayerApp(opened: Uri?) {
    val context = LocalContext.current
    val permission = if (Build.VERSION.SDK_INT >= 33) {
        Manifest.permission.READ_MEDIA_AUDIO
    } else {
        Manifest.permission.READ_EXTERNAL_STORAGE
    }
    var granted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED
        )
    }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            try {
                context.contentResolver.takePersistableUriPermission(
                    uri,
                    android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION,
                )
            } catch (_: SecurityException) {
            }
        }
    }

    var tracks by remember { mutableStateOf(listOf<Track>()) }
    var index by remember { mutableIntStateOf(-1) }
    var playing by remember { mutableStateOf(false) }
    var progress by remember { mutableFloatStateOf(0f) }
    var duration by remember { mutableFloatStateOf(0f) }

    val player = remember {
        ExoPlayer.Builder(context).build().apply {
            addListener(object : Player.Listener {
                override fun onIsPlayingChanged(isPlaying: Boolean) {
                    playing = isPlaying
                }

                override fun onPlaybackStateChanged(playbackState: Int) {
                    if (playbackState == Player.STATE_ENDED && index + 1 < tracks.size) {
                        index += 1
                    }
                }
            })
        }
    }

    DisposableEffect(Unit) {
        onDispose { player.release() }
    }

    LaunchedEffect(granted) {
        if (granted) tracks = loadTracks(context)
    }
    LaunchedEffect(opened) {
        if (opened != null) {
            tracks = listOf(Track(0, opened.lastPathSegment ?: "Файл", opened)) + tracks
            index = 0
        }
    }
    LaunchedEffect(index, tracks) {
        val track = tracks.getOrNull(index) ?: return@LaunchedEffect
        player.setMediaItem(MediaItem.fromUri(track.uri))
        player.prepare()
        player.play()
    }
    LaunchedEffect(player) {
        while (true) {
            duration = player.duration.coerceAtLeast(0).toFloat()
            progress = player.currentPosition.toFloat()
            delay(400)
        }
    }

    MaterialTheme(colorScheme = darkColorScheme(primary = Green, background = Bg, surface = Card)) {
        Column(
            Modifier
                .fillMaxSize()
                .background(Bg)
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Мой плеер", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Bold)
            Text("Музыка с телефона, без Сбера", color = Color(0xFF8AA297))

            if (!granted) {
                Button(onClick = { ask.launch(permission) }) { Text("Разрешить доступ к музыке") }
            }

            Button(onClick = { picker.launch(arrayOf("audio/*")) }) { Text("Открыть файл") }

            val current = tracks.getOrNull(index)
            Text(current?.name ?: "Ничего не играет", color = Green, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)

            Slider(
                value = if (duration > 0) progress / duration else 0f,
                onValueChange = { player.seekTo((it * duration).toLong()) },
                modifier = Modifier.fillMaxWidth(),
            )
            Text(formatMs(progress.toLong()) + " / " + formatMs(duration.toLong()), color = Color(0xFF8AA297))

            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically) {
                Button(onClick = { if (index > 0) index -= 1 }) { Text("⏮") }
                Button(onClick = {
                    if (index < 0 && tracks.isNotEmpty()) index = 0
                    else if (player.isPlaying) player.pause() else player.play()
                }) { Text(if (playing) "Пауза" else "Играть") }
                Button(onClick = { if (index + 1 < tracks.size) index += 1 }) { Text("⏭") }
            }

            LazyColumn(Modifier.fillMaxSize()) {
                itemsIndexed(tracks) { i, track ->
                    Text(
                        track.name,
                        color = if (i == index) Green else Color.White,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { index = i }
                            .padding(vertical = 10.dp),
                    )
                }
            }
        }
    }
}

private fun formatMs(ms: Long): String {
    if (ms <= 0) return "0:00"
    val total = ms / 1000
    return "${total / 60}:${(total % 60).toString().padStart(2, '0')}"
}

private fun loadTracks(context: android.content.Context): List<Track> {
    val result = mutableListOf<Track>()
    val collection = MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
    val projection = arrayOf(MediaStore.Audio.Media._ID, MediaStore.Audio.Media.DISPLAY_NAME)
    val sort = "${MediaStore.Audio.Media.DATE_ADDED} DESC"
    context.contentResolver.query(collection, projection, null, null, sort)?.use { cursor ->
        val idCol = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
        val nameCol = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.DISPLAY_NAME)
        while (cursor.moveToNext()) {
            val id = cursor.getLong(idCol)
            result += Track(id, cursor.getString(nameCol) ?: "Трек", ContentUris.withAppendedId(collection, id))
        }
    }
    return result
}
