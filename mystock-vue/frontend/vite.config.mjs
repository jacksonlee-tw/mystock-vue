import path from 'node:path';
import fs from 'node:fs';
import { PrimeVueResolver } from '@primevue/auto-import-resolver';
import vue from '@vitejs/plugin-vue';
import Components from 'unplugin-vue-components/vite';
import { defineConfig } from 'vite';

function fixViteHashPlugin() {
    return {
        name: 'fix-vite-hash',
        enforce: 'pre',
        resolveId(source) {
            if (!source) return null;
            // 跳過 CSS 及字型檔案中的正常 hash 錨點
            if (/\.(css|eot|ttf|woff|woff2|svg)$/i.test(source.split('?')[0])) {
                return null;
            }
            if (source.includes('#ai-agent')) {
                const parts = source.split('#ai-agent');
                if (parts.length > 2) {
                    return parts[0] + '#ai-agent' + parts[1];
                }
            }
            return null;
        },
        load(id) {
            if (!id) return null;
            if (/\.(css|eot|ttf|woff|woff2|svg)$/i.test(id.split('?')[0])) {
                return null;
            }
            if (id.includes('#ai-agent')) {
                const parts = id.split('#ai-agent');
                if (parts.length > 2) {
                    const cleanPath = parts[0] + '#ai-agent' + parts[1];
                    if (fs.existsSync(cleanPath) && !fs.statSync(cleanPath).isDirectory()) {
                        return fs.readFileSync(cleanPath, 'utf-8');
                    }
                }
            }
            return null;
        }
    };
}

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [
        fixViteHashPlugin(),
        vue(),
        Components({
            resolvers: [PrimeVueResolver()]
        })
    ],
    resolve: {
        alias: {
            '@': path.resolve(process.cwd(), 'src')
        }
    },
    server: {
        fs: {
            strict: false
        }
    }
});
