from flask import Flask, render_template, request
import random
import statistics

app = Flask(__name__)

def run_simulation(env_params):
    llegada_lambda = env_params['lambda']
    servicio_mu = env_params['mu']
    num_cajas = env_params['s']
    tiempo_sim = env_params['horizonte']
    
    reloj = 0.0
    cajas_libres_en = [0.0] * num_cajas 
    tiempos_sistema = [] 
    
    while reloj < tiempo_sim:
        t_entre_llegadas = random.expovariate(llegada_lambda)
        reloj += t_entre_llegadas
        if reloj > tiempo_sim: break

        cajas_libres_en.sort() 
        tiempo_inicio_servicio = max(reloj, cajas_libres_en[0])
        t_servicio = random.expovariate(servicio_mu)
        tiempo_salida = tiempo_inicio_servicio + t_servicio
        cajas_libres_en[0] = tiempo_salida
        tiempos_sistema.append(tiempo_salida - reloj)

    return tiempos_sistema

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            min_cajas = int(request.form['min_cajas'])
            max_cajas = int(request.form['max_cajas'])
            if min_cajas < 1: min_cajas = 1
            if max_cajas < min_cajas: max_cajas = min_cajas

            tasa_llegada = float(request.form['lambda'])
            tasa_servicio = float(request.form['mu'])
            costo_caja = float(request.form['c_caja'])      
            costo_espera = float(request.form['c_espera'])  
            costo_sla = float(request.form['c_sla'])        
            sla_target = float(request.form['sla_target'])  
            sla_time = float(request.form['sla_time'])      
            replicas = int(request.form.get('replicas', 10)) 
            tiempo_total_sim = 480 
            
            resultados_globales = []

            for s in range(min_cajas, max_cajas + 1): 
                datos_replicas = []
                for r in range(1, replicas + 1):
                    params = {'lambda': tasa_llegada, 'mu': tasa_servicio, 's': s, 'horizonte': tiempo_total_sim}
                    tiempos = run_simulation(params)
                    
                    if tiempos:
                        avg_t = statistics.mean(tiempos)
                        cumplen_sla = sum(1 for t in tiempos if t <= sla_time)
                        pct_sla = (cumplen_sla / len(tiempos)) * 100
                        total_clientes = len(tiempos)
                    else:
                        avg_t = 0; pct_sla = 100; total_clientes = 0

                    costo_operativo = costo_caja * s * tiempo_total_sim
                    costo_esp_rep = costo_espera * (avg_t * total_clientes)
                    penalizacion = 0
                    if pct_sla < sla_target:
                        penalizacion = costo_sla * (sla_target - pct_sla)
                    
                    ct_replica = costo_operativo + costo_esp_rep + penalizacion

                    datos_replicas.append({
                        'n_replica': r,
                        'avg_t': avg_t,
                        'pct_sla': pct_sla,
                        'clientes': total_clientes,
                        'costo_op': costo_operativo,
                        'costo_esp': costo_esp_rep,
                        'costo_penal': penalizacion,
                        'costo_total': ct_replica
                    })

                mean_costo = statistics.mean([d['costo_total'] for d in datos_replicas])
                mean_sla = statistics.mean([d['pct_sla'] for d in datos_replicas])
                mean_tiempo = statistics.mean([d['avg_t'] for d in datos_replicas])
                mean_clientes = statistics.mean([d['clientes'] for d in datos_replicas])
                
                mean_op = statistics.mean([d['costo_op'] for d in datos_replicas])
                mean_esp = statistics.mean([d['costo_esp'] for d in datos_replicas])
                mean_penal = statistics.mean([d['costo_penal'] for d in datos_replicas])
                
                stdev_costo = statistics.stdev([d['costo_total'] for d in datos_replicas]) if replicas > 1 else 0

                resultados_globales.append({
                    'cajas': s,
                    'resumen': {
                        'mean_costo': round(mean_costo, 2),
                        'stdev_costo': round(stdev_costo, 2),
                        'mean_sla': round(mean_sla, 2),
                        'mean_tiempo': round(mean_tiempo, 2),
                        'mean_clientes': round(mean_clientes, 1),
                        'mean_op': round(mean_op, 2),
                        'mean_esp': round(mean_esp, 2),
                        'mean_penal': round(mean_penal, 2),
                        'cumple_sla': mean_sla >= sla_target
                    },
                    'detalles': datos_replicas
                })

            if resultados_globales:
                min_cost = min(r['resumen']['mean_costo'] for r in resultados_globales)
                for r in resultados_globales:
                    r['es_mejor'] = (r['resumen']['mean_costo'] == min_cost)

            return render_template('results.html', resultados=resultados_globales)

        except Exception as e:
            return f"<h3 style='color:red'>Error: {e}</h3>"

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)