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
    // mermaid 內部以動態 import() 載入各圖表類型子模組（flowchart/sequence/gantt...），
    // 開發模式下若不強制預先打包，esbuild 依賴預建構與執行期動態載入的子模組可能解析成
    // 兩份不同的 mermaid 實例，造成節點文字量測失敗、圖表節點文字消失（渲染成預設空白方塊）。
    optimizeDeps: {
        include: ['mermaid']
    },
    server: {
        fs: {
            strict: false
        }
    }
});
