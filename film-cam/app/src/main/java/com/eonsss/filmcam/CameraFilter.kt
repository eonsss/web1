package com.eonsss.filmcam

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.Paint
import android.graphics.PorterDuff
import android.graphics.PorterDuffXfermode
import android.graphics.RadialGradient
import android.graphics.Shader
import android.graphics.BitmapShader
import kotlin.math.hypot
import kotlin.random.Random

/**
 * 감성 필터 하나의 정의.
 * - [matrix]: 색감 (채도/대비/톤/페이드)
 * - [vignette]: 가장자리 어두움 (0..1)
 * - [grain]: 필름 입자 (0..1, 저장되는 사진에만 적용)
 */
class CameraFilter(
    val name: String,
    val matrix: ColorMatrix = ColorMatrix(),
    val vignette: Float = 0f,
    val grain: Float = 0f,
) {
    val colorFilter: ColorMatrixColorFilter get() = ColorMatrixColorFilter(matrix)

    /** 촬영된 비트맵에 필터를 입혀 새 비트맵을 반환한다. */
    fun apply(src: Bitmap): Bitmap {
        val out = Bitmap.createBitmap(src.width, src.height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(out)
        canvas.drawBitmap(src, 0f, 0f, Paint(Paint.FILTER_BITMAP_FLAG).apply {
            colorFilter = this@CameraFilter.colorFilter
        })

        val w = src.width.toFloat()
        val h = src.height.toFloat()

        if (vignette > 0f) {
            val shader = RadialGradient(
                w / 2, h / 2, hypot(w, h) / 2 * 0.95f,
                intArrayOf(Color.TRANSPARENT, Color.TRANSPARENT, Color.argb((vignette * 200).toInt(), 0, 0, 0)),
                floatArrayOf(0f, 0.45f, 1f),
                Shader.TileMode.CLAMP,
            )
            canvas.drawRect(0f, 0f, w, h, Paint().apply { this.shader = shader })
        }

        if (grain > 0f) {
            canvas.drawRect(0f, 0f, w, h, Paint().apply {
                shader = BitmapShader(noiseTile, Shader.TileMode.REPEAT, Shader.TileMode.REPEAT)
                xfermode = PorterDuffXfermode(PorterDuff.Mode.OVERLAY)
                alpha = (grain * 255).toInt().coerceIn(0, 255)
            })
        }
        return out
    }

    companion object {
        private val noiseTile: Bitmap by lazy {
            val size = 256
            val rnd = Random(42)
            val px = IntArray(size * size) {
                val v = rnd.nextInt(256)
                Color.rgb(v, v, v)
            }
            Bitmap.createBitmap(px, size, size, Bitmap.Config.ARGB_8888)
        }

        // ---- ColorMatrix 빌더 ----
        private fun saturation(s: Float) = ColorMatrix().apply { setSaturation(s) }

        private fun contrast(c: Float): ColorMatrix {
            val t = 128f * (1 - c)
            return ColorMatrix(floatArrayOf(
                c, 0f, 0f, 0f, t,
                0f, c, 0f, 0f, t,
                0f, 0f, c, 0f, t,
                0f, 0f, 0f, 1f, 0f,
            ))
        }

        /** 채널별 배율 (따뜻함/차가움 톤) */
        private fun tint(r: Float, g: Float, b: Float) = ColorMatrix().apply { setScale(r, g, b, 1f) }

        /** 어두운 부분을 들어올려 빛바랜 느낌을 준다. */
        private fun fade(a: Float): ColorMatrix {
            val s = 1 - a
            val t = 255f * a
            return ColorMatrix(floatArrayOf(
                s, 0f, 0f, 0f, t,
                0f, s, 0f, 0f, t,
                0f, 0f, s, 0f, t,
                0f, 0f, 0f, 1f, 0f,
            ))
        }

        private fun brightness(offset: Float) = ColorMatrix(floatArrayOf(
            1f, 0f, 0f, 0f, offset,
            0f, 1f, 0f, 0f, offset,
            0f, 0f, 1f, 0f, offset,
            0f, 0f, 0f, 1f, 0f,
        ))

        private fun chain(vararg ms: ColorMatrix) = ColorMatrix().apply { ms.forEach { postConcat(it) } }

        val all: List<CameraFilter> = listOf(
            CameraFilter("원본"),
            CameraFilter("필름",
                chain(saturation(0.9f), contrast(1.05f), tint(1.04f, 1f, 0.94f), fade(0.04f)),
                vignette = 0.4f, grain = 0.25f),
            CameraFilter("빈티지",
                chain(saturation(0.6f), contrast(0.95f), tint(1.08f, 1f, 0.82f), fade(0.08f)),
                vignette = 0.5f, grain = 0.3f),
            CameraFilter("몽환",
                chain(saturation(0.85f), contrast(0.85f), tint(1.03f, 0.98f, 1.06f), fade(0.1f), brightness(8f))),
            CameraFilter("노을",
                chain(saturation(1.2f), contrast(1.05f), tint(1.15f, 0.98f, 0.8f)),
                vignette = 0.3f),
            CameraFilter("새벽",
                chain(saturation(0.8f), contrast(0.95f), tint(0.9f, 1f, 1.12f), fade(0.05f))),
            CameraFilter("민트",
                chain(saturation(0.9f), contrast(0.95f), tint(0.92f, 1.05f, 1.02f), fade(0.06f), brightness(4f))),
            CameraFilter("폴라로이드",
                chain(saturation(0.8f), contrast(0.9f), tint(1.05f, 1.02f, 0.92f), fade(0.12f), brightness(6f)),
                vignette = 0.2f),
            CameraFilter("로모",
                chain(saturation(1.3f), contrast(1.25f), tint(1.05f, 1f, 0.95f)),
                vignette = 0.8f, grain = 0.2f),
            CameraFilter("흑백",
                chain(saturation(0f), contrast(1.15f)),
                vignette = 0.4f, grain = 0.4f),
        )
    }
}
