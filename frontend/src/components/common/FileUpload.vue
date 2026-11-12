<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, UploadFilled } from '@element-plus/icons-vue'
import { uploadFile } from '@/api/file'

const props = defineProps({
  modelValue: { type: String, default: '' },
  bizType: { type: String, required: true },
  bizId: { type: [Number, String], default: null },
  imageOnly: { type: Boolean, default: false },
  accept: { type: String, default: '' },
  maxSizeMb: { type: Number, default: 20 },
  tip: { type: String, default: '' },
  /** 头像用圆形，其余用方形 */
  round: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'uploaded'])

const uploading = ref(false)
const percent = ref(0)
const fileName = ref('')

const allowed = computed(
  () =>
    props.accept ||
    (props.imageOnly
      ? '.jpg,.jpeg,.png,.gif,.webp'
      : '.jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.xls,.xlsx,.zip')
)

const isImage = computed(() => /\.(jpe?g|png|gif|webp)(\?.*)?$/i.test(props.modelValue))

function suffixOf(name) {
  const index = name.lastIndexOf('.')
  return index >= 0 ? name.slice(index).toLowerCase() : ''
}

function beforeUpload(file) {
  const suffix = suffixOf(file.name)
  const allowedList = allowed.value.split(',').map((item) => item.trim().toLowerCase())
  if (!allowedList.includes(suffix)) {
    ElMessage.error(`不支持的文件类型：${suffix || '无扩展名'}`)
    return false
  }
  if (file.size > props.maxSizeMb * 1024 * 1024) {
    ElMessage.error(`文件不能超过 ${props.maxSizeMb}MB`)
    return false
  }
  return true
}

async function doUpload(options) {
  const file = options.file
  uploading.value = true
  percent.value = 0
  fileName.value = file.name

  try {
    const data = await uploadFile(file, {
      bizType: props.bizType,
      bizId: props.bizId,
      onProgress: (value) => {
        percent.value = value
      }
    })
    emit('update:modelValue', data.url)
    emit('uploaded', data)
    ElMessage.success('上传成功')
  } catch (error) {
    ElMessage.error(error.message || '上传失败，请重试')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="uploader" :class="{ 'is-round': round }">
    <el-upload
      class="uploader__trigger"
      :show-file-list="false"
      :accept="allowed"
      :before-upload="beforeUpload"
      :http-request="doUpload"
      :disabled="uploading"
    >
      <div v-if="modelValue && isImage" class="preview">
        <img :src="modelValue" alt="预览" />
        <div class="preview__mask">{{ uploading ? `${percent}%` : '重新上传' }}</div>
      </div>

      <div v-else-if="modelValue" class="file-chip">
        <el-icon><UploadFilled /></el-icon>
        <span>{{ fileName || '已上传文件' }}</span>
      </div>

      <div v-else class="placeholder">
        <el-icon class="placeholder__icon"><Plus v-if="!uploading" /><UploadFilled v-else /></el-icon>
        <span>{{ uploading ? `上传中 ${percent}%` : '点击上传' }}</span>
      </div>
    </el-upload>

    <p v-if="tip" class="uploader__tip">{{ tip }}</p>
    <el-progress
      v-if="uploading"
      class="uploader__progress"
      :percentage="percent"
      :show-text="false"
      :stroke-width="4"
    />
  </div>
</template>

<style scoped>
.uploader__trigger :deep(.el-upload) {
  width: 100%;
}

.preview,
.placeholder,
.file-chip {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px dashed #cdd6e0;
  border-radius: 10px;
  background: #f8fafc;
  color: #909399;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.preview,
.placeholder {
  width: 120px;
  height: 120px;
}

.is-round .preview,
.is-round .placeholder {
  border-radius: 50%;
}

.preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview__mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: rgb(15 23 42 / 55%);
  opacity: 0;
  transition: opacity 0.2s;
}

.preview:hover .preview__mask {
  opacity: 1;
}

.placeholder {
  flex-direction: column;
  gap: 6px;
}

.placeholder__icon {
  font-size: 22px;
}

.file-chip {
  gap: 8px;
  width: 100%;
  max-width: 320px;
  padding: 10px 14px;
  justify-content: flex-start;
}

.file-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.uploader__tip {
  margin-top: 6px;
  font-size: 12px;
  color: #b1b3b8;
}

.uploader__progress {
  width: 120px;
  margin-top: 6px;
}
</style>
