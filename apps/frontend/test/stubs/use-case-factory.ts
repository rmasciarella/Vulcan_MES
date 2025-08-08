export const UseCaseFactory = {
  getInstance() {
    return {
      getJobUseCases: async () => ({
        fetchJobs: async () => [],
        fetchJobsPaginated: async () => ({ hasMore: false, items: [] }),
        getJobCount: async () => 0,
        fetchJobById: async () => null,
        updateJobStatus: async (args: any) => ({ instance_id: args.id, status: args.status }),
        fetchJobsByTemplateId: async () => [],
        fetchJobsByDueDateRange: async () => [],
      }),
    }
  },
}
