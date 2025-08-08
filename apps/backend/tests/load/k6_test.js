/**
 * k6 Load Testing Script for Vulcan Engine Scheduling API
 *
 * Usage:
 *   k6 run k6_test.js
 *   k6 run --vus 100 --duration 30s k6_test.js
 *   k6 run --config k6_config.json k6_test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';
import { randomIntBetween, randomItem } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Custom metrics
const errorRate = new Rate('errors');
const schedulingDuration = new Trend('scheduling_duration');
const optimizationDuration = new Trend('optimization_duration');
const cacheHits = new Counter('cache_hits');
const activeJobs = new Gauge('active_jobs');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

// Test scenarios
export const options = {
    scenarios: {
        // Smoke test
        smoke: {
            executor: 'constant-vus',
            vus: 1,
            duration: '1m',
            tags: { scenario: 'smoke' },
        },

        // Load test
        load: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '2m', target: 50 },   // Ramp up
                { duration: '5m', target: 50 },   // Stay at 50
                { duration: '2m', target: 100 },  // Ramp to 100
                { duration: '5m', target: 100 },  // Stay at 100
                { duration: '2m', target: 0 },    // Ramp down
            ],
            tags: { scenario: 'load' },
            startTime: '2m',
        },

        // Stress test
        stress: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '2m', target: 100 },
                { duration: '5m', target: 100 },
                { duration: '2m', target: 200 },
                { duration: '5m', target: 200 },
                { duration: '2m', target: 300 },
                { duration: '5m', target: 300 },
                { duration: '2m', target: 0 },
            ],
            tags: { scenario: 'stress' },
            startTime: '18m',
        },

        // Spike test
        spike: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '10s', target: 100 },
                { duration: '1m', target: 100 },
                { duration: '10s', target: 500 },  // Spike!
                { duration: '3m', target: 500 },
                { duration: '10s', target: 100 },
                { duration: '3m', target: 100 },
                { duration: '10s', target: 0 },
            ],
            tags: { scenario: 'spike' },
            startTime: '42m',
        },
    },

    thresholds: {
        'http_req_duration': ['p(95)<500', 'p(99)<1000'],
        'http_req_duration{endpoint:job_list}': ['p(95)<200'],
        'http_req_duration{endpoint:job_get}': ['p(95)<100'],
        'http_req_duration{endpoint:schedule_create}': ['p(95)<5000'],
        'errors': ['rate<0.05'],  // Error rate < 5%
        'http_req_failed': ['rate<0.05'],
    },
};

// Test data
const jobData = {
    names: ['Manufacturing Order', 'Assembly Job', 'Production Batch', 'Custom Order'],
    priorities: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    skills: ['welding', 'machining', 'assembly', 'inspection', 'programming'],
    statuses: ['pending', 'scheduled', 'in_progress', 'completed'],
};

// Shared state
const state = {
    jobIds: [],
    scheduleIds: [],
    operatorIds: [],
    token: null,
};

// Helper functions
function getHeaders() {
    return {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...(state.token && { 'Authorization': `Bearer ${state.token}` }),
    };
}

function handleResponse(response, name) {
    const success = check(response, {
        [`${name}: status is 200-299`]: (r) => r.status >= 200 && r.status < 300,
        [`${name}: response time < 1000ms`]: (r) => r.timings.duration < 1000,
    });

    errorRate.add(!success);

    if (response.headers['X-Cache-Hit'] === 'true') {
        cacheHits.add(1);
    }

    return success;
}

// Test functions
export function setup() {
    console.log(`Starting test against ${BASE_URL}`);

    // Optionally login and get token
    // const loginRes = http.post(`${BASE_URL}/api/v1/login`, JSON.stringify({
    //     username: 'test@example.com',
    //     password: 'password',
    // }), { headers: getHeaders() });

    // if (loginRes.status === 200) {
    //     const data = JSON.parse(loginRes.body);
    //     return { token: data.access_token };
    // }

    return {};
}

export default function main() {
    group('Job Operations', () => {
        // Create job
        group('Create Job', () => {
            const payload = {
                name: randomItem(jobData.names) + '_' + Date.now(),
                priority: randomItem(jobData.priorities),
                due_date: new Date(Date.now() + randomIntBetween(1, 30) * 24 * 60 * 60 * 1000).toISOString(),
                tasks: Array.from({ length: randomIntBetween(5, 20) }, (_, i) => ({
                    name: `Task_${i}`,
                    duration: randomIntBetween(30, 180),
                    skill_required: randomItem(jobData.skills),
                    skill_level: randomIntBetween(1, 3),
                })),
            };

            const response = http.post(
                `${BASE_URL}${API_PREFIX}/jobs`,
                JSON.stringify(payload),
                {
                    headers: getHeaders(),
                    tags: { endpoint: 'job_create' },
                }
            );

            if (handleResponse(response, 'Create Job')) {
                const data = JSON.parse(response.body);
                if (data.id) {
                    state.jobIds.push(data.id);
                    // Keep only last 100 IDs
                    if (state.jobIds.length > 100) {
                        state.jobIds = state.jobIds.slice(-100);
                    }
                    activeJobs.add(state.jobIds.length);
                }
            }
        });

        sleep(randomIntBetween(1, 3));

        // Get job
        if (state.jobIds.length > 0) {
            group('Get Job', () => {
                const jobId = randomItem(state.jobIds);
                const response = http.get(
                    `${BASE_URL}${API_PREFIX}/jobs/${jobId}`,
                    {
                        headers: getHeaders(),
                        tags: { endpoint: 'job_get' },
                    }
                );

                handleResponse(response, 'Get Job');
            });
        }

        sleep(randomIntBetween(1, 2));

        // List jobs
        group('List Jobs', () => {
            const params = {
                limit: randomItem([10, 20, 50]),
                offset: randomIntBetween(0, 100),
            };

            if (Math.random() > 0.5) {
                params.status = randomItem(jobData.statuses);
            }

            const response = http.get(
                `${BASE_URL}${API_PREFIX}/jobs?` + Object.entries(params)
                    .map(([k, v]) => `${k}=${v}`)
                    .join('&'),
                {
                    headers: getHeaders(),
                    tags: { endpoint: 'job_list' },
                }
            );

            handleResponse(response, 'List Jobs');
        });
    });

    sleep(randomIntBetween(2, 5));

    group('Scheduling Operations', () => {
        // Schedule job
        if (state.jobIds.length > 0 && Math.random() > 0.7) {
            group('Schedule Job', () => {
                const jobId = randomItem(state.jobIds);
                const payload = {
                    job_id: jobId,
                    optimization_level: randomItem(['quick', 'normal', 'thorough']),
                    constraints: {
                        max_makespan: randomIntBetween(5, 20) * 24 * 60,
                    },
                };

                const startTime = Date.now();
                const response = http.post(
                    `${BASE_URL}${API_PREFIX}/schedules`,
                    JSON.stringify(payload),
                    {
                        headers: getHeaders(),
                        tags: { endpoint: 'schedule_create' },
                        timeout: '30s',
                    }
                );

                schedulingDuration.add(Date.now() - startTime);

                if (handleResponse(response, 'Schedule Job')) {
                    const data = JSON.parse(response.body);
                    if (data.id) {
                        state.scheduleIds.push(data.id);
                        if (state.scheduleIds.length > 50) {
                            state.scheduleIds = state.scheduleIds.slice(-50);
                        }
                    }
                }
            });
        }

        // Get schedule
        if (state.scheduleIds.length > 0) {
            group('Get Schedule', () => {
                const scheduleId = randomItem(state.scheduleIds);
                const response = http.get(
                    `${BASE_URL}${API_PREFIX}/schedules/${scheduleId}`,
                    {
                        headers: getHeaders(),
                        tags: { endpoint: 'schedule_get' },
                    }
                );

                handleResponse(response, 'Get Schedule');
            });
        }

        // Optimize schedule
        if (state.scheduleIds.length > 0 && Math.random() > 0.8) {
            group('Optimize Schedule', () => {
                const scheduleId = randomItem(state.scheduleIds);
                const payload = {
                    focus: randomItem(['cost', 'makespan', 'balanced']),
                    max_iterations: randomIntBetween(100, 1000),
                };

                const startTime = Date.now();
                const response = http.post(
                    `${BASE_URL}${API_PREFIX}/schedules/${scheduleId}/optimize`,
                    JSON.stringify(payload),
                    {
                        headers: getHeaders(),
                        tags: { endpoint: 'schedule_optimize' },
                        timeout: '60s',
                    }
                );

                optimizationDuration.add(Date.now() - startTime);
                handleResponse(response, 'Optimize Schedule');
            });
        }
    });

    sleep(randomIntBetween(1, 3));

    // Metrics and monitoring
    if (Math.random() > 0.9) {
        group('Monitoring', () => {
            const response = http.get(
                `${BASE_URL}${API_PREFIX}/metrics/performance`,
                {
                    headers: getHeaders(),
                    tags: { endpoint: 'metrics' },
                }
            );

            handleResponse(response, 'Get Metrics');
        });
    }

    // Health check
    if (Math.random() > 0.95) {
        const response = http.get(
            `${BASE_URL}/health`,
            { tags: { endpoint: 'health' } }
        );

        check(response, {
            'Health check OK': (r) => r.status === 200,
        });
    }
}

export function teardown(data) {
    console.log('Test completed');

    // Print custom metrics summary
    console.log(`Cache hit rate: ${cacheHits.value || 0} hits`);
    console.log(`Active jobs at end: ${state.jobIds.length}`);
    console.log(`Active schedules at end: ${state.scheduleIds.length}`);
}

// Custom scenarios for specific testing
export function stressTest() {
    // Aggressive testing pattern
    for (let i = 0; i < 10; i++) {
        main();
        sleep(0.1);
    }
}

export function cacheBusterTest() {
    // Test cache invalidation
    const jobId = randomItem(state.jobIds);

    // Rapid repeated requests to same resource
    for (let i = 0; i < 20; i++) {
        http.get(`${BASE_URL}${API_PREFIX}/jobs/${jobId}`, {
            headers: getHeaders(),
            tags: { test: 'cache_buster' },
        });
        sleep(0.05);
    }
}

export function concurrentSchedulingTest() {
    // Test concurrent scheduling operations
    const batch = http.batch(
        state.jobIds.slice(0, 10).map(jobId => ({
            method: 'POST',
            url: `${BASE_URL}${API_PREFIX}/schedules`,
            body: JSON.stringify({
                job_id: jobId,
                optimization_level: 'quick',
            }),
            params: {
                headers: getHeaders(),
                tags: { test: 'concurrent_scheduling' },
            },
        }))
    );

    batch.forEach((response, index) => {
        check(response, {
            [`Concurrent schedule ${index}: OK`]: (r) => r.status < 400,
        });
    });
}
