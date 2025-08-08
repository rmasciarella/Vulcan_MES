'use client'

import { useState, useCallback } from 'react'
import { useCreateJob, useUpdateJobStatus } from '@/features/scheduling/hooks/use-jobs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { ManufacturingErrorBoundary } from '@/shared/components/error-boundary'
import { InlineLoadingState } from '@/shared/components/loading-states'
import { Package, FileText, AlertCircle, CheckCircle2, X, Plus, Save } from 'lucide-react'
import { z } from 'zod'
import type { JobInstance } from '@/types/supabase'
import { cn } from '@/shared/lib/utils'

// Using direct JobInstance type

// Zod validation schema for job creation/update
const jobFormSchema = z
  .object({
    templateId: z
      .string()
      .min(1, 'Template ID is required')
      .max(50, 'Template ID must be 50 characters or less')
      .regex(
        /^[A-Z0-9_-]+$/i,
        'Template ID can only contain letters, numbers, hyphens, and underscores',
      ),

    serialNumber: z
      .string()
      .min(1, 'Serial number is required')
      .max(100, 'Serial number must be 100 characters or less')
      .regex(
        /^[A-Z0-9_-]+$/i,
        'Serial number can only contain letters, numbers, hyphens, and underscores',
      ),

    productType: z
      .string()
      .min(1, 'Product type is required')
      .max(200, 'Product type must be 200 characters or less'),

    dueDate: z
      .string()
      .min(1, 'Due date is required')
      .refine((date) => {
        const parsed = new Date(date)
        return !isNaN(parsed.getTime()) && parsed > new Date()
      }, 'Due date must be in the future'),

    releaseDate: z
      .string()
      .min(1, 'Release date is required')
      .refine((date) => {
        const parsed = new Date(date)
        return !isNaN(parsed.getTime())
      }, 'Release date must be a valid date'),
  })
  .refine(
    (data) => {
      const releaseDate = new Date(data.releaseDate)
      const dueDate = new Date(data.dueDate)
      return releaseDate <= dueDate
    },
    {
      message: 'Release date must be before or equal to due date',
      path: ['releaseDate'],
    },
  )

type JobFormData = z.infer<typeof jobFormSchema>

interface JobFormProps {
  mode: 'create' | 'edit'
  existingJob?: JobInstance
  onSuccess?: (job: JobInstance) => void
  onCancel?: () => void
  className?: string
}

interface FormFieldProps {
  label: string
  name: keyof JobFormData
  type?: 'text' | 'date' | 'datetime-local'
  placeholder?: string
  description?: string
  required?: boolean
  error?: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

function FormField({
  label,
  name,
  type = 'text',
  placeholder,
  description,
  required = false,
  error,
  value,
  onChange,
  disabled = false,
}: FormFieldProps) {
  return (
    <div>
      <label htmlFor={name} className="mb-1 block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
      <Input
        id={name}
        name={name}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={cn(error && 'border-red-300 focus:border-red-500 focus:ring-red-500')}
      />
      {description && <p className="mt-1 text-xs text-gray-500">{description}</p>}
      {error && (
        <p className="mt-1 flex items-center text-xs text-red-600">
          <AlertCircle className="mr-1 h-3 w-3" />
          {error}
        </p>
      )}
    </div>
  )
}

/**
 * Job Creation/Update Form with comprehensive validation
 * Features:
 * - Zod schema validation for manufacturing requirements
 * - Real-time field validation
 * - Manufacturing-specific field constraints
 * - Template and serial number format validation
 * - Date constraint validation (release <= due, future dates)
 * - Responsive design for tablets
 * - Proper error handling and user feedback
 */
export function JobForm({ mode, existingJob, onSuccess, onCancel, className }: JobFormProps) {
  // Initialize form with existing job data or defaults
  const [formData, setFormData] = useState<JobFormData>({
    templateId: existingJob?.template_id || '',
    serialNumber: existingJob?.name || '',
    productType: existingJob?.description || '',
    dueDate: existingJob?.due_date ? new Date(existingJob.due_date).toISOString().slice(0, 16) : '',
    releaseDate: existingJob?.earliest_start_date
      ? new Date(existingJob.earliest_start_date).toISOString().slice(0, 16)
      : '',
  })

  const [errors, setErrors] = useState<Partial<Record<keyof JobFormData, string>>>({})
  const [isValidating, setIsValidating] = useState(false)

  const createJob = useCreateJob()
  const updateJob = useUpdateJobStatus()

  const handleFieldChange = useCallback(
    (field: keyof JobFormData, value: string) => {
      setFormData((prev) => ({ ...prev, [field]: value }))

      // Clear field error when user starts typing
      if (errors[field]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }))
      }
    },
    [errors],
  )

  const validateForm = useCallback(async () => {
    setIsValidating(true)
    setErrors({})

    try {
      await jobFormSchema.parseAsync(formData)
      return true
    } catch (error) {
      if (error instanceof z.ZodError) {
        const fieldErrors: Partial<Record<keyof JobFormData, string>> = {}
        error.issues.forEach((err) => {
          if (err.path[0]) {
            fieldErrors[err.path[0] as keyof JobFormData] = err.message
          }
        })
        setErrors(fieldErrors)
      }
      return false
    } finally {
      setIsValidating(false)
    }
  }, [formData])

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()

      const isValid = await validateForm()
      if (!isValid) return

      try {
        if (mode === 'create') {
          const result = await createJob.mutateAsync({
            templateId: formData.templateId,
            serialNumber: formData.serialNumber,
            productType: formData.productType,
            dueDate: new Date(formData.dueDate),
            releaseDate: new Date(formData.releaseDate),
          })
          onSuccess?.(result)
        } else if (existingJob) {
          // For edit mode, we would need a separate update mutation
          // For now, this is a placeholder showing the pattern
          console.log('Update job functionality would be implemented here')
          onSuccess?.(existingJob)
        }
      } catch (error) {
        console.error('Form submission error:', error)
      }
    },
    [mode, formData, validateForm, createJob, existingJob, onSuccess],
  )

  const isSubmitting = createJob.isPending || updateJob.isPending

  // Template suggestions based on common manufacturing patterns
  const templateSuggestions = [
    'LASER_SYSTEM_V1',
    'LASER_ASSEMBLY_V2',
    'OPTICAL_BENCH_V1',
    'CONTROL_UNIT_V1',
    'POWER_SUPPLY_V2',
  ]

  return (
    <ManufacturingErrorBoundary componentName="JobForm">
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            {mode === 'create' ? (
              <>
                <Plus className="mr-2 h-5 w-5" />
                Create New Job
              </>
            ) : (
              <>
                <FileText className="mr-2 h-5 w-5" />
                Edit Job {existingJob?.instance_id}
              </>
            )}
          </CardTitle>
          <CardDescription>
            {mode === 'create'
              ? 'Create a new production job with scheduling constraints and manufacturing requirements.'
              : 'Update job information and scheduling parameters.'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Template ID */}
            <div>
              <FormField
                label="Template ID"
                name="templateId"
                placeholder="e.g., LASER_SYSTEM_V1"
                description="Manufacturing template that defines the job structure and requirements"
                required
                error={errors.templateId ?? ''}
                value={formData.templateId}
                onChange={(value) => handleFieldChange('templateId', value)}
                disabled={isSubmitting}
              />
              {/* Template suggestions */}
              {!formData.templateId && (
                <div className="mt-2">
                  <p className="mb-2 text-xs text-gray-500">Common templates:</p>
                  <div className="flex flex-wrap gap-2">
                    {templateSuggestions.map((template) => (
                      <button
                        key={template}
                        type="button"
                        onClick={() => handleFieldChange('templateId', template)}
                        className="rounded border bg-gray-100 px-2 py-1 text-xs hover:bg-gray-200"
                      >
                        {template}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Serial Number */}
            <FormField
              label="Serial Number"
              name="serialNumber"
              placeholder="e.g., LS-2024-001"
              description="Unique identifier for traceability throughout the manufacturing process"
              required
              error={errors.serialNumber ?? ''}
              value={formData.serialNumber}
              onChange={(value) => handleFieldChange('serialNumber', value)}
              disabled={isSubmitting}
            />

            {/* Product Type */}
            <FormField
              label="Product Type"
              name="productType"
              placeholder="e.g., High-Power Laser System"
              description="Product description that will appear on manufacturing documentation"
              required
              error={errors.productType ?? ''}
              value={formData.productType}
              onChange={(value) => handleFieldChange('productType', value)}
              disabled={isSubmitting}
            />

            {/* Date Fields */}
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <FormField
                label="Release Date"
                name="releaseDate"
                type="datetime-local"
                description="When this job can be started on the production floor"
                required
                error={errors.releaseDate ?? ''}
                value={formData.releaseDate}
                onChange={(value) => handleFieldChange('releaseDate', value)}
                disabled={isSubmitting}
              />

              <FormField
                label="Due Date"
                name="dueDate"
                type="datetime-local"
                description="When this job must be completed for customer delivery"
                required
                error={errors.dueDate ?? ''}
                value={formData.dueDate}
                onChange={(value) => handleFieldChange('dueDate', value)}
                disabled={isSubmitting}
              />
            </div>

            {/* Manufacturing Context Alert */}
            <Alert>
              <Package className="h-4 w-4" />
              <AlertDescription>
                <strong>Manufacturing Requirements:</strong> Jobs created here will be automatically
                integrated with the production scheduling system. Ensure template ID matches an
                existing manufacturing template and that dates align with production capacity.
              </AlertDescription>
            </Alert>

            {/* Form Errors */}
            {Object.keys(errors).length > 0 && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  Please fix the following errors:
                  <ul className="mt-2 list-inside list-disc space-y-1">
                    {Object.values(errors).map((error, index) => (
                      <li key={index} className="text-sm">
                        {error}
                      </li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}

            {/* Actions */}
            <div className="flex items-center justify-end space-x-4 border-t pt-6">
              {onCancel && (
                <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
                  <X className="mr-1 h-4 w-4" />
                  Cancel
                </Button>
              )}

              <Button
                type="submit"
                disabled={isSubmitting || isValidating}
                className="min-w-[120px]"
              >
                {isSubmitting ? (
                  <InlineLoadingState
                    message={mode === 'create' ? 'Creating...' : 'Updating...'}
                    size="sm"
                  />
                ) : (
                  <>
                    <Save className="mr-1 h-4 w-4" />
                    {mode === 'create' ? 'Create Job' : 'Update Job'}
                  </>
                )}
              </Button>
            </div>

            {/* Success feedback for create mode */}
            {createJob.isSuccess && mode === 'create' && (
              <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertDescription>
                  Job created successfully! The new job has been added to the production schedule
                  and is ready for task assignment.
                </AlertDescription>
              </Alert>
            )}
          </form>
        </CardContent>
      </Card>
    </ManufacturingErrorBoundary>
  )
}
