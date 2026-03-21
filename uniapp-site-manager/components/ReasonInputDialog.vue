<template>
	<view v-if="visible" class="reason-dialog-mask" @click.self="handleMaskClose">
		<view class="reason-dialog" @click.stop>
			<view class="reason-dialog__header">
				<view class="reason-dialog__title-wrap">
					<text class="reason-dialog__title">{{ title }}</text>
					<text v-if="message" class="reason-dialog__message">{{ message }}</text>
				</view>
				<view
					class="reason-dialog__close u-pressable-subtle"
					:class="{ disabled: submitting }"
					@click="handleClose"
				>
					<uni-icons type="closeempty" size="20" color="#6b7280" />
				</view>
			</view>

			<view class="reason-dialog__body">
				<view class="reason-dialog__field">
					<view class="reason-dialog__field-top">
						<text class="reason-dialog__label">{{ label }}</text>
						<text class="reason-dialog__count mono">{{ currentLength }}/{{ maxlength }}</text>
					</view>
					<textarea
						class="reason-dialog__textarea"
						:value="modelValue"
						:placeholder="placeholder"
						:maxlength="maxlength"
						:focus="visible"
						auto-height
						cursor-spacing="28"
						:disabled="submitting"
						@input="handleInput"
						@confirm="handleConfirm"
					/>
					<text v-if="helperText" class="reason-dialog__helper">{{ helperText }}</text>
					<text v-if="errorText" class="reason-dialog__error">{{ errorText }}</text>
				</view>
			</view>

			<view class="reason-dialog__footer">
				<button class="u-btn u-btn-secondary u-pressable" :disabled="submitting" @click="handleClose">
					{{ cancelText }}
				</button>
				<button class="u-btn u-btn-danger u-pressable" :disabled="submitting" @click="handleConfirm">
					{{ submitting ? submittingText : confirmText }}
				</button>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { computed } from 'vue'

	const props = defineProps({
		visible: {
			type: Boolean,
			default: false,
		},
		modelValue: {
			type: String,
			default: '',
		},
		title: {
			type: String,
			default: '',
		},
		message: {
			type: String,
			default: '',
		},
		label: {
			type: String,
			default: '',
		},
		placeholder: {
			type: String,
			default: '',
		},
		helperText: {
			type: String,
			default: '',
		},
		errorText: {
			type: String,
			default: '',
		},
		confirmText: {
			type: String,
			default: '',
		},
		cancelText: {
			type: String,
			default: '',
		},
		submittingText: {
			type: String,
			default: '',
		},
		submitting: {
			type: Boolean,
			default: false,
		},
		maxlength: {
			type: Number,
			default: 200,
		},
	})

	const emit = defineEmits(['update:modelValue', 'close', 'confirm'])

	const currentLength = computed(() => String(props.modelValue || '').length)

	const handleInput = (event) => {
		emit('update:modelValue', String(event?.detail?.value || ''))
	}

	const handleClose = () => {
		if (props.submitting) return
		emit('close')
	}

	const handleMaskClose = () => {
		handleClose()
	}

	const handleConfirm = () => {
		if (props.submitting) return
		emit('confirm')
	}
</script>

<style scoped lang="scss">
	.reason-dialog-mask {
		position: fixed;
		inset: 0;
		z-index: 1200;
		background: rgba(15, 23, 42, 0.42);
		backdrop-filter: blur(8px);
		display: flex;
		align-items: flex-end;
		justify-content: center;
		padding: 20px 14px calc(20px + env(safe-area-inset-bottom));
	}

	.reason-dialog {
		width: 100%;
		max-width: 520px;
		border-radius: 24px;
		overflow: hidden;
		background:
			radial-gradient(520px 180px at 100% 0%, rgba(251, 146, 60, 0.13), transparent 58%),
			radial-gradient(420px 220px at 0% 0%, rgba(239, 68, 68, 0.10), transparent 56%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.94));
		border: 1px solid rgba(229, 231, 235, 0.9);
		box-shadow: 0 24px 60px rgba(15, 23, 42, 0.24);
		animation: reasonDialogIn 180ms ease-out;
	}

	@keyframes reasonDialogIn {
		from {
			transform: translateY(18px);
			opacity: 0;
		}
		to {
			transform: translateY(0);
			opacity: 1;
		}
	}

	.reason-dialog__header {
		padding: 18px 18px 12px;
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}

	.reason-dialog__title-wrap {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-width: 0;
	}

	.reason-dialog__title {
		font-size: 17px;
		font-weight: 900;
		color: #111827;
	}

	.reason-dialog__message {
		font-size: 12px;
		line-height: 1.6;
		color: #6b7280;
	}

	.reason-dialog__close {
		width: 38px;
		height: 38px;
		border-radius: 12px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(243, 244, 246, 0.95);
		flex-shrink: 0;
	}

	.reason-dialog__close.disabled {
		opacity: 0.55;
	}

	.reason-dialog__body {
		padding: 0 18px 14px;
	}

	.reason-dialog__field {
		padding: 14px;
		border-radius: 18px;
		border: 1px solid rgba(229, 231, 235, 0.95);
		background: rgba(248, 250, 252, 0.92);
	}

	.reason-dialog__field-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}

	.reason-dialog__label {
		font-size: 13px;
		font-weight: 800;
		color: #111827;
	}

	.reason-dialog__count {
		font-size: 11px;
		color: #9ca3af;
	}

	.reason-dialog__textarea {
		width: 100%;
		min-height: 124px;
		margin-top: 12px;
		padding: 12px 14px;
		box-sizing: border-box;
		border-radius: 16px;
		background: #ffffff;
		border: 1px solid rgba(209, 213, 219, 0.95);
		font-size: 14px;
		line-height: 1.6;
		color: #111827;
	}

	.reason-dialog__helper {
		display: block;
		margin-top: 10px;
		font-size: 11px;
		line-height: 1.5;
		color: #6b7280;
	}

	.reason-dialog__error {
		display: block;
		margin-top: 10px;
		font-size: 11px;
		line-height: 1.5;
		font-weight: 700;
		color: #dc2626;
	}

	.reason-dialog__footer {
		padding: 0 18px 18px;
		display: flex;
		gap: 10px;
	}

	.reason-dialog__footer :deep(.u-btn) {
		flex: 1;
		height: 46px;
	}

	.mono {
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
	}
</style>
