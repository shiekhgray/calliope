package com.dresdengray.calliope.ui.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.dresdengray.calliope.data.api.model.SimilarityWeightsRequest
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

/**
 * Bottom sheet for adjusting the 9 similarity weights.
 * Weights are 1–10 integer values loaded from GET /auth/me and saved via PUT /auth/similarity-weights.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SoundMatchingSheet(
    viewModel: SettingsViewModel,
    onDismiss: () -> Unit
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val scope = rememberCoroutineScope()
    val meState by viewModel.meState.collectAsState()

    // Weights — floats for slider, converted to Int on save
    var tempo by remember { mutableStateOf(5f) }
    var timbralVariation by remember { mutableStateOf(5f) }
    var dynamicRange by remember { mutableStateOf(5f) }
    var brightness by remember { mutableStateOf(5f) }
    var timbre by remember { mutableStateOf(5f) }
    var loudness by remember { mutableStateOf(5f) }
    var harmony by remember { mutableStateOf(5f) }
    var chordMovement by remember { mutableStateOf(5f) }
    var tonal by remember { mutableStateOf(5f) }

    var isSaving by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var saveSuccess by remember { mutableStateOf(false) }

    // Populate sliders when me data arrives
    LaunchedEffect(meState) {
        meState?.let { me ->
            tempo = me.simWeightTempo.toFloat()
            timbralVariation = me.simWeightTimbralVariation.toFloat()
            dynamicRange = me.simWeightDynamicRange.toFloat()
            brightness = me.simWeightBrightness.toFloat()
            timbre = me.simWeightTimbre.toFloat()
            loudness = me.simWeightLoudness.toFloat()
            harmony = me.simWeightHarmony.toFloat()
            chordMovement = me.simWeightChordMovement.toFloat()
            tonal = me.simWeightTonal.toFloat()
        }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Text(
                text = "Sound Matching",
                style = MaterialTheme.typography.titleLarge
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = "Adjust how similar tracks are matched. Higher = more weight for that quality.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(16.dp))

            if (meState == null) {
                CircularProgressIndicator()
                Spacer(Modifier.height(24.dp))
            } else {
                // Rhythm group
                WeightGroupHeader("Rhythm")
                WeightSlider("Tempo", tempo) { tempo = it }
                WeightSlider("Beat Complexity", timbralVariation) { timbralVariation = it }
                WeightSlider("Dynamic Range", dynamicRange) { dynamicRange = it }

                Spacer(Modifier.height(16.dp))

                // Timbre group
                WeightGroupHeader("Timbre")
                WeightSlider("Brightness", brightness) { brightness = it }
                WeightSlider("Texture", timbre) { timbre = it }
                WeightSlider("Loudness", loudness) { loudness = it }

                Spacer(Modifier.height(16.dp))

                // Harmony group
                WeightGroupHeader("Harmony")
                WeightSlider("Key / Mode", harmony) { harmony = it }
                WeightSlider("Chord Complexity", chordMovement) { chordMovement = it }
                WeightSlider("Tonal Stability", tonal) { tonal = it }

                errorMessage?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = it,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                if (saveSuccess) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = "Saved.",
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.bodySmall
                    )
                }

                Spacer(Modifier.height(16.dp))

                Row(modifier = Modifier.fillMaxWidth()) {
                    TextButton(onClick = onDismiss) { Text("Close") }
                    Spacer(Modifier.weight(1f))
                    Button(
                        onClick = {
                            isSaving = true
                            saveSuccess = false
                            errorMessage = null
                            scope.launch {
                                viewModel.updateSimilarityWeights(
                                    SimilarityWeightsRequest(
                                        simWeightTimbre = timbre.roundToInt(),
                                        simWeightTimbralVariation = timbralVariation.roundToInt(),
                                        simWeightHarmony = harmony.roundToInt(),
                                        simWeightChordMovement = chordMovement.roundToInt(),
                                        simWeightTempo = tempo.roundToInt(),
                                        simWeightLoudness = loudness.roundToInt(),
                                        simWeightDynamicRange = dynamicRange.roundToInt(),
                                        simWeightBrightness = brightness.roundToInt(),
                                        simWeightTonal = tonal.roundToInt()
                                    )
                                ).onSuccess { saveSuccess = true }
                                    .onFailure { e -> errorMessage = e.message ?: "Failed to save." }
                                isSaving = false
                            }
                        },
                        enabled = !isSaving
                    ) {
                        Text("Save")
                    }
                }
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}

@Composable
private fun WeightGroupHeader(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.primary
    )
    Spacer(Modifier.height(4.dp))
}

@Composable
private fun WeightSlider(label: String, value: Float, onValueChange: (Float) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f)
        )
        Text(
            text = value.roundToInt().toString(),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
    Slider(
        value = value,
        onValueChange = onValueChange,
        valueRange = 1f..10f,
        steps = 8, // 9 positions: 1,2,...,10 with 8 internal steps
        modifier = Modifier.fillMaxWidth()
    )
}
