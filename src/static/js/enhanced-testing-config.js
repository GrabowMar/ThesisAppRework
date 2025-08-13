/**
 * Enhanced Testing Configuration Management
 */

class TestingConfigManager {
    constructor() {
        this.currentConfig = this.getDefaultConfig();
        this.presets = this.getPresets();
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.updatePreview();
        this.validateConfiguration();
    }

    getDefaultConfig() {
        return {
            static: {
                bandit: {
                    confidence: 'medium',
                    severity: 'medium',
                    format: 'json',
                    skip_tests: [],
                    exclude_paths: [],
                    recursive: true,
                    ignore_nosec: false,
                    verbose: false
                },
                pylint: {
                    disable: [],
                    confidence: ['HIGH', 'INFERENCE'],
                    max_line_length: 100,
                    fail_under: 5.0,
                    load_plugins: [],
                    reports: true,
                    score: true,
                    errors_only: false
                },
                eslint: {
                    env: 'node',
                    ecma_version: '2025',
                    max_warnings: 50,
                    parser: 'espree',
                    source_type: 'module',
                    jsx: true,
                    cache: true,
                    fix: false
                }
            },
            performance: {
                apache_bench: {
                    requests: 1000,
                    concurrency: 10,
                    timeout: 30,
                    timelimit: null,
                    keep_alive: true,
                    content_type: 'application/x-www-form-urlencoded',
                    ssl_protocol: '',
                    verbosity: true,
                    enable_ssl: false,
                    csv_output: true,
                    disable_percentiles: false,
                    gnuplot_output: false
                }
            },
            ai: {
                openrouter: {
                    model: 'anthropic/claude-3.5-sonnet',
                    temperature: 0.7,
                    max_tokens: 4000,
                    top_p: 0.9,
                    frequency_penalty: 0,
                    presence_penalty: 0,
                    top_k: null,
                    reasoning_enabled: false,
                    reasoning_effort: 'medium',
                    include_reasoning: true,
                    stream: false,
                    function_calling: false
                }
            }
        };
    }

    getPresets() {
        return {
            security_focused: {
                static: {
                    bandit: {
                        confidence: 'low',
                        severity: 'low',
                        format: 'json',
                        skip_tests: [],
                        exclude_paths: [],
                        recursive: true,
                        ignore_nosec: false,
                        verbose: false,
                        msg_template: null,
                        output_file: null
                    },
                    pylint: {
                        disable: [],
                        confidence: ['UNDEFINED', 'INFERENCE', 'INFERENCE_FAILURE'],
                        max_line_length: 120,
                        fail_under: 7.0,
                        load_plugins: ['pylint.extensions.check_elif'],
                        naming_style: 'snake_case',
                        reports: true,
                        score: true,
                        errors_only: false,
                        rcfile: null,
                        msg_template: null
                    },
                    eslint: {
                        env: 'both',
                        ecma_version: 'latest',
                        max_warnings: 10,
                        parser: 'espree',
                        source_type: 'module',
                        jsx: false,
                        cache: false,
                        cache_location: null,
                        fix: false,
                        fix_dry_run: false,
                        print_config: false
                    }
                },
                performance: {
                    apache_bench: {
                        requests: 500,
                        concurrency: 5,
                        timeout: 60,
                        timelimit: null,
                        keep_alive: false,
                        content_type: 'application/x-www-form-urlencoded',
                        ssl_protocol: '',
                        verbosity: false,
                        enable_ssl: false,
                        csv_output: false,
                        disable_percentiles: false,
                        gnuplot_output: false,
                        percentiles: [50, 90, 95],
                        show_median: false,
                        show_confidence: false
                    }
                },
                ai: {
                    openrouter: {
                        model: 'anthropic/claude-3.5-sonnet',
                        temperature: 0.3,
                        max_tokens: 6000,
                        top_p: 0.9,
                        frequency_penalty: 0.0,
                        presence_penalty: 0.0,
                        top_k: null,
                        reasoning_enabled: true,
                        reasoning_effort: 'high',
                        include_reasoning: true,
                        stream: false,
                        function_calling: true
                    }
                }
            },
            performance_focused: {
                static: {
                    bandit: {
                        confidence: 'high',
                        severity: 'medium',
                        format: 'json',
                        skip_tests: [],
                        exclude_paths: ['tests/'],
                        recursive: true,
                        ignore_nosec: false,
                        verbose: false,
                        msg_template: null,
                        output_file: null
                    },
                    pylint: {
                        disable: ['C0103', 'R0903'],
                        confidence: ['HIGH'],
                        max_line_length: 100,
                        fail_under: 6.0,
                        load_plugins: [],
                        naming_style: 'snake_case',
                        reports: false,
                        score: true,
                        errors_only: false,
                        rcfile: null,
                        msg_template: null
                    },
                    eslint: {
                        env: 'node',
                        ecma_version: '2024',
                        max_warnings: 25,
                        parser: 'espree',
                        source_type: 'module',
                        jsx: false,
                        cache: true,
                        cache_location: '.eslintcache',
                        fix: false,
                        fix_dry_run: false,
                        print_config: false
                    }
                },
                performance: {
                    apache_bench: {
                        requests: 5000,
                        concurrency: 50,
                        timeout: 120,
                        timelimit: 300,
                        keep_alive: true,
                        content_type: 'application/x-www-form-urlencoded',
                        ssl_protocol: 'TLS1.2',
                        verbosity: true,
                        enable_ssl: false,
                        csv_output: true,
                        disable_percentiles: false,
                        gnuplot_output: true,
                        percentiles: [50, 75, 90, 95, 99],
                        show_median: true,
                        show_confidence: true
                    }
                },
                ai: {
                    openrouter: {
                        model: 'openai/gpt-4o',
                        temperature: 0.5,
                        max_tokens: 3000,
                        top_p: 0.95,
                        frequency_penalty: 0.1,
                        presence_penalty: 0.1,
                        top_k: 40,
                        reasoning_enabled: false,
                        reasoning_effort: 'medium',
                        include_reasoning: false,
                        stream: false,
                        function_calling: false
                    }
                }
            },
            code_quality: {
                static: {
                    bandit: {
                        confidence: 'medium',
                        severity: 'medium',
                        format: 'json',
                        skip_tests: [],
                        exclude_paths: [],
                        recursive: true,
                        ignore_nosec: false,
                        verbose: true,
                        msg_template: '{abspath}:{line}: {test_id}[bandit]: {severity}: {msg}',
                        output_file: null
                    },
                    pylint: {
                        disable: [],
                        confidence: ['CONTROL_FLOW', 'INFERENCE'],
                        max_line_length: 88,
                        fail_under: 8.0,
                        load_plugins: ['pylint.extensions.check_elif', 'pylint.extensions.bad_builtin'],
                        naming_style: 'snake_case',
                        reports: true,
                        score: true,
                        errors_only: false,
                        rcfile: null,
                        msg_template: '{path}:{line}:{column}: {msg_id}: {msg} ({symbol})'
                    },
                    eslint: {
                        env: 'node',
                        ecma_version: '2022',
                        max_warnings: 25,
                        parser: '@typescript-eslint/parser',
                        source_type: 'module',
                        jsx: false,
                        cache: true,
                        cache_location: '.eslintcache',
                        fix: false,
                        fix_dry_run: true,
                        print_config: false
                    }
                },
                performance: {
                    apache_bench: {
                        requests: 1000,
                        concurrency: 10,
                        timeout: 60,
                        timelimit: null,
                        keep_alive: false,
                        content_type: 'application/x-www-form-urlencoded',
                        ssl_protocol: '',
                        verbosity: false,
                        enable_ssl: false,
                        csv_output: false,
                        disable_percentiles: false,
                        gnuplot_output: false,
                        percentiles: [50, 90, 95],
                        show_median: false,
                        show_confidence: false
                    }
                },
                ai: {
                    openrouter: {
                        model: 'anthropic/claude-3.5-sonnet',
                        temperature: 0.4,
                        max_tokens: 5000,
                        top_p: 0.9,
                        frequency_penalty: 0.0,
                        presence_penalty: 0.0,
                        top_k: null,
                        reasoning_enabled: true,
                        reasoning_effort: 'medium',
                        include_reasoning: false,
                        stream: false,
                        function_calling: true
                    }
                }
            },
            ai_comprehensive: {
                static: {
                    bandit: {
                        confidence: 'medium',
                        severity: 'medium',
                        format: 'sarif',
                        skip_tests: [],
                        exclude_paths: [],
                        recursive: true,
                        ignore_nosec: false,
                        verbose: true,
                        msg_template: null,
                        output_file: 'bandit-report.sarif'
                    },
                    pylint: {
                        disable: [],
                        confidence: ['CONTROL_FLOW', 'INFERENCE', 'INFERENCE_FAILURE', 'UNDEFINED'],
                        max_line_length: 100,
                        fail_under: 7.5,
                        load_plugins: ['pylint.extensions.check_elif', 'pylint.extensions.bad_builtin', 'pylint.extensions.comparison_placement'],
                        naming_style: 'snake_case',
                        reports: true,
                        score: true,
                        errors_only: false,
                        rcfile: null,
                        msg_template: null
                    },
                    eslint: {
                        env: 'es2025',
                        ecma_version: '2025',
                        max_warnings: 50,
                        parser: '@typescript-eslint/parser',
                        source_type: 'module',
                        jsx: true,
                        cache: true,
                        cache_location: '.eslintcache',
                        fix: false,
                        fix_dry_run: false,
                        print_config: true
                    }
                },
                performance: {
                    apache_bench: {
                        requests: 2000,
                        concurrency: 20,
                        timeout: 90,
                        timelimit: 180,
                        keep_alive: true,
                        content_type: 'application/json',
                        ssl_protocol: 'TLS1.3',
                        verbosity: true,
                        enable_ssl: true,
                        csv_output: true,
                        disable_percentiles: false,
                        gnuplot_output: true,
                        percentiles: [50, 75, 90, 95, 98, 99],
                        show_median: true,
                        show_confidence: true
                    }
                },
                ai: {
                    openrouter: {
                        model: 'anthropic/claude-3.5-sonnet',
                        temperature: 0.6,
                        max_tokens: 8000,
                        top_p: 0.9,
                        frequency_penalty: 0.1,
                        presence_penalty: 0.1,
                        top_k: 50,
                        reasoning_enabled: true,
                        reasoning_effort: 'maximum',
                        include_reasoning: true,
                        stream: false,
                        function_calling: true
                    }
                }
            }
        };
    }

    setupEventListeners() {
        // Form change listeners
        const forms = ['staticConfigForm', 'performanceConfigForm', 'aiConfigForm'];
        forms.forEach(formId => {
            const form = document.getElementById(formId);
            if (form) {
                form.addEventListener('change', () => {
                    this.updateConfigFromForms();
                    this.updatePreview();
                    this.validateConfiguration();
                });
                form.addEventListener('input', () => {
                    this.updateConfigFromForms();
                    this.updatePreview();
                });
            }
        });

        // Range input updates
        document.querySelectorAll('input[type="range"]').forEach(range => {
            range.addEventListener('input', (e) => {
                const output = e.target.nextElementSibling;
                if (output && output.tagName === 'OUTPUT') {
                    output.value = e.target.value;
                }
            });
        });

        // Model selection change listener - handled by template script
        // App selection change listener - handled by template script

        // Batch selection listeners
        document.querySelectorAll('.batch-model-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateBatchSummary();
            });
        });
    }

    updateConfigFromForms() {
        // Static analysis config
        const staticForm = document.getElementById('staticConfigForm');
        if (staticForm) {
            const formData = new FormData(staticForm);
            
            // Bandit config
            this.currentConfig.static.bandit.confidence = formData.get('bandit_confidence') || 'medium';
            this.currentConfig.static.bandit.severity = formData.get('bandit_severity') || 'medium';
            this.currentConfig.static.bandit.format = formData.get('bandit_format') || 'json';
            this.currentConfig.static.bandit.skip_tests = formData.get('bandit_skip_tests') 
                ? formData.get('bandit_skip_tests').split(',').map(s => s.trim()).filter(s => s)
                : [];
            this.currentConfig.static.bandit.exclude_paths = formData.get('bandit_exclude_paths')
                ? formData.get('bandit_exclude_paths').split(',').map(s => s.trim()).filter(s => s)
                : [];
            this.currentConfig.static.bandit.recursive = formData.has('bandit_recursive');
            this.currentConfig.static.bandit.ignore_nosec = formData.has('bandit_ignore_nosec');
            this.currentConfig.static.bandit.verbose = formData.has('bandit_verbose');

            // Pylint config
            this.currentConfig.static.pylint.disable = formData.get('pylint_disable')
                ? formData.get('pylint_disable').split(',').map(s => s.trim()).filter(s => s)
                : [];
            const confidenceSelect = staticForm.querySelector('[name="pylint_confidence"]');
            this.currentConfig.static.pylint.confidence = Array.from(confidenceSelect.selectedOptions)
                .map(option => option.value);
            this.currentConfig.static.pylint.max_line_length = parseInt(formData.get('pylint_max_line_length')) || 100;
            this.currentConfig.static.pylint.fail_under = parseFloat(formData.get('pylint_fail_under')) || 5.0;
            this.currentConfig.static.pylint.load_plugins = formData.get('pylint_load_plugins')
                ? formData.get('pylint_load_plugins').split(',').map(s => s.trim()).filter(s => s)
                : [];
            this.currentConfig.static.pylint.reports = formData.has('pylint_reports');
            this.currentConfig.static.pylint.score = formData.has('pylint_score');
            this.currentConfig.static.pylint.errors_only = formData.has('pylint_errors_only');

            // ESLint config
            this.currentConfig.static.eslint.env = formData.get('eslint_env') || 'node';
            this.currentConfig.static.eslint.ecma_version = formData.get('eslint_ecma_version') || '2025';
            this.currentConfig.static.eslint.max_warnings = parseInt(formData.get('eslint_max_warnings')) || 50;
            this.currentConfig.static.eslint.parser = formData.get('eslint_parser') || 'espree';
            this.currentConfig.static.eslint.source_type = formData.get('eslint_source_type') || 'module';
            this.currentConfig.static.eslint.jsx = formData.has('eslint_jsx');
            this.currentConfig.static.eslint.cache = formData.has('eslint_cache');
            this.currentConfig.static.eslint.fix = formData.has('eslint_fix');
        }

        // Performance config
        const performanceForm = document.getElementById('performanceConfigForm');
        if (performanceForm) {
            const formData = new FormData(performanceForm);
            
            this.currentConfig.performance.apache_bench.requests = parseInt(formData.get('ab_requests')) || 1000;
            this.currentConfig.performance.apache_bench.concurrency = parseInt(formData.get('ab_concurrency')) || 10;
            this.currentConfig.performance.apache_bench.timeout = parseInt(formData.get('ab_timeout')) || 30;
            this.currentConfig.performance.apache_bench.timelimit = formData.get('ab_timelimit') 
                ? parseInt(formData.get('ab_timelimit')) : null;
            this.currentConfig.performance.apache_bench.keep_alive = formData.get('ab_keep_alive') === 'true';
            this.currentConfig.performance.apache_bench.content_type = formData.get('ab_content_type') || 'application/x-www-form-urlencoded';
            this.currentConfig.performance.apache_bench.ssl_protocol = formData.get('ab_ssl_protocol') || '';
            this.currentConfig.performance.apache_bench.verbosity = formData.has('ab_verbosity');
            this.currentConfig.performance.apache_bench.enable_ssl = formData.has('ab_enable_ssl');
            this.currentConfig.performance.apache_bench.csv_output = formData.has('ab_csv_output');
            this.currentConfig.performance.apache_bench.disable_percentiles = formData.has('ab_disable_percentiles');
            this.currentConfig.performance.apache_bench.gnuplot_output = formData.has('ab_gnuplot_output');
        }

        // AI config
        const aiForm = document.getElementById('aiConfigForm');
        if (aiForm) {
            const formData = new FormData(aiForm);
            
            this.currentConfig.ai.openrouter.model = formData.get('openrouter_model') || 'anthropic/claude-3.5-sonnet';
            this.currentConfig.ai.openrouter.temperature = parseFloat(formData.get('openrouter_temperature')) || 0.7;
            this.currentConfig.ai.openrouter.max_tokens = parseInt(formData.get('openrouter_max_tokens')) || 4000;
            this.currentConfig.ai.openrouter.top_p = parseFloat(formData.get('openrouter_top_p')) || 0.9;
            this.currentConfig.ai.openrouter.frequency_penalty = parseFloat(formData.get('openrouter_frequency_penalty')) || 0;
            this.currentConfig.ai.openrouter.presence_penalty = parseFloat(formData.get('openrouter_presence_penalty')) || 0;
            this.currentConfig.ai.openrouter.top_k = formData.get('openrouter_top_k') 
                ? parseInt(formData.get('openrouter_top_k')) : null;
            this.currentConfig.ai.openrouter.reasoning_enabled = formData.has('openrouter_reasoning_enabled');
            this.currentConfig.ai.openrouter.reasoning_effort = formData.get('openrouter_reasoning_effort') || 'medium';
            this.currentConfig.ai.openrouter.include_reasoning = formData.has('openrouter_include_reasoning');
            this.currentConfig.ai.openrouter.stream = formData.has('openrouter_stream');
            this.currentConfig.ai.openrouter.function_calling = formData.has('openrouter_function_calling');
        }
    }

    updatePreview() {
        const previewElement = document.getElementById('configJSON');
        if (previewElement) {
            previewElement.textContent = JSON.stringify(this.currentConfig, null, 2);
        }
    }

    validateConfiguration() {
        const statusElement = document.getElementById('validationStatus');
        if (!statusElement) return;

        const validations = [
            {
                name: 'Static analysis configuration',
                valid: this.validateStaticConfig()
            },
            {
                name: 'Performance configuration',
                valid: this.validatePerformanceConfig()
            },
            {
                name: 'AI configuration',
                valid: this.validateAIConfig()
            }
        ];

        statusElement.innerHTML = validations.map(v => `
            <div class="d-flex align-items-center mb-2">
                <i class="fas ${v.valid ? 'fa-check text-success' : 'fa-times text-danger'} me-2"></i>
                <span>${v.name} ${v.valid ? 'valid' : 'invalid'}</span>
            </div>
        `).join('');
    }

    validateStaticConfig() {
        const static = this.currentConfig.static;
        return static.bandit.confidence && 
               static.pylint.max_line_length > 0 && 
               static.eslint.max_warnings >= 0;
    }

    validatePerformanceConfig() {
        const perf = this.currentConfig.performance.apache_bench;
        return perf.requests > 0 && 
               perf.concurrency > 0 && 
               perf.timeout > 0;
    }

    validateAIConfig() {
        const ai = this.currentConfig.ai.openrouter;
        return ai.model && 
               ai.temperature >= 0 && ai.temperature <= 2 &&
               ai.max_tokens > 0;
    }

    loadPreset(presetName) {
        if (this.presets[presetName]) {
            this.currentConfig = JSON.parse(JSON.stringify(this.presets[presetName]));
            this.populateFormsFromConfig();
            this.updatePreview();
            this.validateConfiguration();
            
            // Show success message
            this.showNotification(`Loaded "${presetName}" preset successfully`, 'success');
        }
    }

    populateFormsFromConfig() {
        // Static form
        const staticForm = document.getElementById('staticConfigForm');
        if (staticForm) {
            const config = this.currentConfig.static;
            
            // Bandit
            staticForm.querySelector('[name="bandit_confidence"]').value = config.bandit.confidence;
            staticForm.querySelector('[name="bandit_severity"]').value = config.bandit.severity;
            staticForm.querySelector('[name="bandit_format"]').value = config.bandit.format || 'json';
            staticForm.querySelector('[name="bandit_skip_tests"]').value = config.bandit.skip_tests?.join(', ') || '';
            staticForm.querySelector('[name="bandit_exclude_paths"]').value = config.bandit.exclude_paths?.join(', ') || '';
            staticForm.querySelector('[name="bandit_recursive"]').checked = config.bandit.recursive;
            staticForm.querySelector('[name="bandit_ignore_nosec"]').checked = config.bandit.ignore_nosec;
            staticForm.querySelector('[name="bandit_verbose"]').checked = config.bandit.verbose;

            // Pylint
            staticForm.querySelector('[name="pylint_disable"]').value = config.pylint.disable?.join(', ') || '';
            const confidenceSelect = staticForm.querySelector('[name="pylint_confidence"]');
            Array.from(confidenceSelect.options).forEach(option => {
                option.selected = config.pylint.confidence?.includes(option.value) || false;
            });
            staticForm.querySelector('[name="pylint_max_line_length"]').value = config.pylint.max_line_length;
            staticForm.querySelector('[name="pylint_fail_under"]').value = config.pylint.fail_under || 5.0;
            staticForm.querySelector('[name="pylint_load_plugins"]').value = config.pylint.load_plugins?.join(', ') || '';
            staticForm.querySelector('[name="pylint_reports"]').checked = config.pylint.reports;
            staticForm.querySelector('[name="pylint_score"]').checked = config.pylint.score;
            staticForm.querySelector('[name="pylint_errors_only"]').checked = config.pylint.errors_only;

            // ESLint
            staticForm.querySelector('[name="eslint_env"]').value = config.eslint.env;
            staticForm.querySelector('[name="eslint_ecma_version"]').value = config.eslint.ecma_version;
            staticForm.querySelector('[name="eslint_max_warnings"]').value = config.eslint.max_warnings;
            staticForm.querySelector('[name="eslint_parser"]').value = config.eslint.parser || 'espree';
            staticForm.querySelector('[name="eslint_source_type"]').value = config.eslint.source_type || 'module';
            staticForm.querySelector('[name="eslint_jsx"]').checked = config.eslint.jsx;
            staticForm.querySelector('[name="eslint_cache"]').checked = config.eslint.cache;
            staticForm.querySelector('[name="eslint_fix"]').checked = config.eslint.fix;
        }

        // Performance form
        const performanceForm = document.getElementById('performanceConfigForm');
        if (performanceForm) {
            const config = this.currentConfig.performance.apache_bench;
            
            performanceForm.querySelector('[name="ab_requests"]').value = config.requests;
            performanceForm.querySelector('[name="ab_concurrency"]').value = config.concurrency;
            performanceForm.querySelector('[name="ab_timeout"]').value = config.timeout;
            performanceForm.querySelector('[name="ab_timelimit"]').value = config.timelimit || '';
            performanceForm.querySelector('[name="ab_keep_alive"]').value = config.keep_alive;
            performanceForm.querySelector('[name="ab_content_type"]').value = config.content_type || '';
            performanceForm.querySelector('[name="ab_ssl_protocol"]').value = config.ssl_protocol || '';
            performanceForm.querySelector('[name="ab_verbosity"]').checked = config.verbosity;
            performanceForm.querySelector('[name="ab_enable_ssl"]').checked = config.enable_ssl;
            performanceForm.querySelector('[name="ab_csv_output"]').checked = config.csv_output;
            performanceForm.querySelector('[name="ab_disable_percentiles"]').checked = config.disable_percentiles;
            performanceForm.querySelector('[name="ab_gnuplot_output"]').checked = config.gnuplot_output;
        }

        // AI form
        const aiForm = document.getElementById('aiConfigForm');
        if (aiForm) {
            const config = this.currentConfig.ai.openrouter;
            
            aiForm.querySelector('[name="openrouter_model"]').value = config.model;
            
            const tempSlider = aiForm.querySelector('[name="openrouter_temperature"]');
            tempSlider.value = config.temperature;
            tempSlider.nextElementSibling.value = config.temperature;
            
            aiForm.querySelector('[name="openrouter_max_tokens"]').value = config.max_tokens;
            
            const topPSlider = aiForm.querySelector('[name="openrouter_top_p"]');
            topPSlider.value = config.top_p;
            topPSlider.nextElementSibling.value = config.top_p;
            
            const freqSlider = aiForm.querySelector('[name="openrouter_frequency_penalty"]');
            freqSlider.value = config.frequency_penalty;
            freqSlider.nextElementSibling.value = config.frequency_penalty;
            
            const presSlider = aiForm.querySelector('[name="openrouter_presence_penalty"]');
            presSlider.value = config.presence_penalty || 0;
            presSlider.nextElementSibling.value = config.presence_penalty || 0;
            
            aiForm.querySelector('[name="openrouter_top_k"]').value = config.top_k || '';
            aiForm.querySelector('[name="openrouter_reasoning_enabled"]').checked = config.reasoning_enabled;
            aiForm.querySelector('[name="openrouter_reasoning_effort"]').value = config.reasoning_effort || 'medium';
            aiForm.querySelector('[name="openrouter_include_reasoning"]').checked = config.include_reasoning;
            aiForm.querySelector('[name="openrouter_stream"]').checked = config.stream;
            aiForm.querySelector('[name="openrouter_function_calling"]').checked = config.function_calling;
        }
    }

    saveConfiguration() {
        const configName = document.getElementById('configName').value;
        if (!configName.trim()) {
            this.showNotification('Please enter a configuration name', 'warning');
            return;
        }

        const savedConfigs = JSON.parse(localStorage.getItem('testingConfigs') || '{}');
        savedConfigs[configName] = this.currentConfig;
        localStorage.setItem('testingConfigs', JSON.stringify(savedConfigs));
        
        this.showNotification(`Configuration "${configName}" saved successfully`, 'success');
        document.getElementById('configName').value = '';
    }

    exportConfiguration() {
        const dataStr = JSON.stringify(this.currentConfig, null, 2);
        const dataBlob = new Blob([dataStr], {type: 'application/json'});
        
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = 'testing-config.json';
        link.click();
        
        this.showNotification('Configuration exported successfully', 'success');
    }

    importConfiguration() {
        document.getElementById('configImport').click();
    }

    handleConfigImport(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const config = JSON.parse(e.target.result);
                this.currentConfig = config;
                this.populateFormsFromConfig();
                this.updatePreview();
                this.validateConfiguration();
                this.showNotification('Configuration imported successfully', 'success');
            } catch (error) {
                this.showNotification('Invalid configuration file', 'error');
            }
        };
        reader.readAsText(file);
    }

    runTestWithConfig() {
        // Send configuration to backend for testing
        fetch('/api/testing/run-with-config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config: this.currentConfig,
                model_slug: document.getElementById('modelSelect')?.value,
                app_number: document.getElementById('appSelect')?.value
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.showNotification('Test started successfully', 'success');
                // Redirect to results page or update UI
                if (data.task_id) {
                    window.location.href = `/testing/results/${data.task_id}`;
                }
            } else {
                this.showNotification(data.error || 'Failed to start test', 'error');
            }
        })
        .catch(error => {
            this.showNotification('Error starting test: ' + error.message, 'error');
        });
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
}

// Global functions for template usage
function loadPreset(presetName) {
    if (window.testingConfigManager) {
        window.testingConfigManager.loadPreset(presetName);
    }
}

function saveConfiguration() {
    if (window.testingConfigManager) {
        window.testingConfigManager.saveConfiguration();
    }
}

function exportConfiguration() {
    if (window.testingConfigManager) {
        window.testingConfigManager.exportConfiguration();
    }
}

function importConfiguration() {
    if (window.testingConfigManager) {
        window.testingConfigManager.importConfiguration();
    }
}

function handleConfigImport(event) {
    if (window.testingConfigManager) {
        window.testingConfigManager.handleConfigImport(event);
    }
}

function runTestWithConfig() {
    if (window.testingConfigManager) {
        window.testingConfigManager.runTestWithConfig();
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('configTabs')) {
        window.testingConfigManager = new TestingConfigManager();
    }
});
