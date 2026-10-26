package com.eonsss.filmcam

import android.Manifest
import android.content.ContentValues
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Matrix
import android.graphics.Paint
import android.os.Bundle
import android.provider.MediaStore
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.AspectRatio
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.eonsss.filmcam.databinding.ActivityMainBinding
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var worker: ExecutorService

    private var imageCapture: ImageCapture? = null
    private var lensFacing = CameraSelector.LENS_FACING_BACK
    private var currentFilter: CameraFilter = CameraFilter.all.first()

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startCamera() else {
                Toast.makeText(this, R.string.need_camera, Toast.LENGTH_LONG).show()
                finish()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        worker = Executors.newSingleThreadExecutor()

        // 색 필터를 실시간 프리뷰에 입히려면 TextureView 기반(COMPATIBLE) 이어야 한다.
        binding.previewView.implementationMode = PreviewView.ImplementationMode.COMPATIBLE

        buildFilterBar()
        applyFilterToPreview(currentFilter)

        binding.shutterButton.setOnClickListener { takePhoto() }
        binding.switchButton.setOnClickListener {
            lensFacing = if (lensFacing == CameraSelector.LENS_FACING_BACK)
                CameraSelector.LENS_FACING_FRONT else CameraSelector.LENS_FACING_BACK
            startCamera()
        }

        if (hasCameraPermission()) startCamera()
        else permissionLauncher.launch(Manifest.permission.CAMERA)
    }

    override fun onDestroy() {
        super.onDestroy()
        worker.shutdown()
    }

    private fun hasCameraPermission() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    // ---------- 필터 UI ----------

    private fun buildFilterBar() {
        val density = resources.displayMetrics.density
        CameraFilter.all.forEach { filter ->
            val chip = TextView(this).apply {
                text = filter.name
                setTextColor(0xFF222222.toInt())
                textSize = 14f
                setPadding((16 * density).toInt(), (8 * density).toInt(), (16 * density).toInt(), (8 * density).toInt())
                setBackgroundResource(R.drawable.chip_bg)
                isSelected = filter === currentFilter
                setOnClickListener { selectFilter(filter) }
                layoutParams = android.widget.LinearLayout.LayoutParams(
                    android.widget.LinearLayout.LayoutParams.WRAP_CONTENT,
                    android.widget.LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply { marginEnd = (8 * density).toInt() }
            }
            binding.filterBar.addView(chip)
        }
    }

    private fun selectFilter(filter: CameraFilter) {
        currentFilter = filter
        for (i in 0 until binding.filterBar.childCount) {
            binding.filterBar.getChildAt(i).isSelected = CameraFilter.all[i] === filter
        }
        applyFilterToPreview(filter)
    }

    private fun applyFilterToPreview(filter: CameraFilter) {
        val paint = Paint().apply { colorFilter = filter.colorFilter }
        binding.previewView.setLayerType(View.LAYER_TYPE_HARDWARE, paint)
        binding.vignetteView.animate().alpha(filter.vignette).setDuration(150).start()
    }

    // ---------- 카메라 ----------

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()

            val preview = Preview.Builder()
                .setTargetAspectRatio(AspectRatio.RATIO_4_3)
                .build()
                .also { it.setSurfaceProvider(binding.previewView.surfaceProvider) }

            val capture = ImageCapture.Builder()
                .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                .setTargetAspectRatio(AspectRatio.RATIO_4_3)
                .build()
            imageCapture = capture

            val selector = CameraSelector.Builder().requireLensFacing(lensFacing).build()
            try {
                provider.unbindAll()
                provider.bindToLifecycle(this, selector, preview, capture)
            } catch (e: Exception) {
                Toast.makeText(this, e.message, Toast.LENGTH_LONG).show()
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun takePhoto() {
        val capture = imageCapture ?: return
        val filter = currentFilter
        val front = lensFacing == CameraSelector.LENS_FACING_FRONT
        binding.shutterButton.isEnabled = false

        capture.takePicture(worker, object : ImageCapture.OnImageCapturedCallback() {
            override fun onCaptureSuccess(image: ImageProxy) {
                val result = try {
                    val rotation = image.imageInfo.rotationDegrees
                    val raw = image.toBitmap()
                    val m = Matrix().apply {
                        postRotate(rotation.toFloat())
                        if (front) postScale(-1f, 1f) // 프리뷰와 동일하게 거울 반전
                    }
                    val oriented = Bitmap.createBitmap(raw, 0, 0, raw.width, raw.height, m, true)
                    filter.apply(oriented).also {
                        if (oriented !== raw) raw.recycle()
                        oriented.recycle()
                    }
                } finally {
                    image.close()
                }
                val ok = save(result)
                result.recycle()
                runOnUiThread {
                    binding.shutterButton.isEnabled = true
                    Toast.makeText(
                        this@MainActivity,
                        if (ok) R.string.saved else R.string.save_failed,
                        Toast.LENGTH_SHORT,
                    ).show()
                }
            }

            override fun onError(exception: ImageCaptureException) {
                runOnUiThread {
                    binding.shutterButton.isEnabled = true
                    Toast.makeText(this@MainActivity, R.string.save_failed, Toast.LENGTH_SHORT).show()
                }
            }
        })
    }

    private fun save(bitmap: Bitmap): Boolean {
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, "FilmCam_${System.currentTimeMillis()}.jpg")
            put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
            put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/FilmCam")
            put(MediaStore.Images.Media.IS_PENDING, 1)
        }
        val resolver = contentResolver
        val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values) ?: return false
        return try {
            resolver.openOutputStream(uri)?.use { bitmap.compress(Bitmap.CompressFormat.JPEG, 95, it) }
            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            true
        } catch (e: Exception) {
            resolver.delete(uri, null, null)
            false
        }
    }
}
