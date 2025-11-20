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
    
    # Ahora guardamos diccionarios para tener W y Wq
    datos_clientes = [] 
    
    while reloj < tiempo_sim:
        t_entre_llegadas = random.expovariate(llegada_lambda)
        reloj += t_entre_llegadas
        if reloj > tiempo_sim: break

        cajas_libres_en.sort() 
        tiempo_inicio_servicio = max(reloj, cajas_libres_en[0])
        
        t_servicio = random.expovariate(servicio_mu)
        tiempo_salida = tiempo_inicio_servicio + t_servicio
        cajas_libres_en[0] = tiempo_salida
        
        # CÁLCULOS:
        # Wq = Tiempo que esperó antes de ser atendido
        tiempo_en_cola = tiempo_inicio_servicio - reloj
        # W = Tiempo total (cola + servicio)
        tiempo_en_sistema = tiempo_salida - reloj
        
        datos_clientes.append({
            'wq': tiempo_en_cola,
            'w': tiempo_en_sistema
        })

    return datos_clientes

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            min_cajas = 1
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
            
            tiempo_total_sim = 480 # tiempo en minutos (8 horas)
            
            resultados_globales = []

            # simulaciones
            for s in range(min_cajas, max_cajas + 1): 
                datos_replicas = []
                for r in range(1, replicas + 1):
                    params = {'lambda': tasa_llegada, 'mu': tasa_servicio, 's': s, 'horizonte': tiempo_total_sim}
                    
                    clientes_sim = run_simulation(params)
                    
                    if clientes_sim:
                        # Extraer listas
                        lista_w = [c['w'] for c in clientes_sim]
                        lista_wq = [c['wq'] for c in clientes_sim]
                        
                        avg_t = statistics.mean(lista_w)
                        avg_wq = statistics.mean(lista_wq)
                        
                        # Ley de Little: Lq = lambda * Wq
                        avg_lq = tasa_llegada * avg_wq
                        
                        cumplen_sla = sum(1 for t in lista_w if t <= sla_time)
                        pct_sla = (cumplen_sla / len(lista_w)) * 100
                        total_clientes = len(lista_w)
                    else:
                        avg_t = 0; avg_wq = 0; avg_lq = 0
                        pct_sla = 100; total_clientes = 0

                    costo_operativo = costo_caja * s * tiempo_total_sim
                    costo_esp_rep = costo_espera * (avg_t * total_clientes)
                    penalizacion = 0
                    if pct_sla < sla_target:
                        penalizacion = costo_sla * (sla_target - pct_sla)
                    
                    ct_replica = costo_operativo + costo_esp_rep + penalizacion

                    datos_replicas.append({
                        'n_replica': r,
                        'avg_t': avg_t,
                        'avg_wq': avg_wq, # Nuevo
                        'avg_lq': avg_lq, # Nuevo
                        'pct_sla': pct_sla,
                        'clientes': total_clientes,
                        'costo_op': costo_operativo,
                        'costo_esp': costo_esp_rep,
                        'costo_penal': penalizacion,
                        'costo_total': ct_replica
                    })

                # promedios globales
                mean_costo = statistics.mean([d['costo_total'] for d in datos_replicas])
                mean_sla = statistics.mean([d['pct_sla'] for d in datos_replicas])
                mean_tiempo = statistics.mean([d['avg_t'] for d in datos_replicas])
                
                # Promedios de cola
                mean_wq = statistics.mean([d['avg_wq'] for d in datos_replicas])
                mean_lq = statistics.mean([d['avg_lq'] for d in datos_replicas])
                
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
                        'mean_wq': round(mean_wq, 2), # Nuevo
                        'mean_lq': round(mean_lq, 1), # Nuevo
                        'mean_clientes': round(mean_clientes, 1),
                        'mean_op': round(mean_op, 2),
                        'mean_esp': round(mean_esp, 2),
                        'mean_penal': round(mean_penal, 2),
                        'cumple_sla': mean_sla >= sla_target
                    },
                    'detalles': datos_replicas
                })

            # datos para graficos
            chart_data = None
            if resultados_globales:
                min_cost = min(r['resumen']['mean_costo'] for r in resultados_globales)
                labels_s = []
                data_costo = []
                data_sla = []
                data_util = []

                for r in resultados_globales:
                    r['es_mejor'] = (r['resumen']['mean_costo'] == min_cost)
                    labels_s.append(r['cajas'])
                    data_costo.append(r['resumen']['mean_costo'])
                    data_sla.append(r['resumen']['mean_sla'])
                    rho = (tasa_llegada / (r['cajas'] * tasa_servicio)) * 100
                    data_util.append(round(rho, 2))

                chart_data = {
                    'labels': labels_s,
                    'costos': data_costo,
                    'slas': data_sla,
                    'utilizacion': data_util,
                    'sla_target': sla_target
                }

            return render_template('results.html', resultados=resultados_globales, chart_data=chart_data)

        except Exception as e:
            return f"<h3 style='color:red'>Error en la simulación: {e}</h3>"


    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)