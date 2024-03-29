class LineChart {
    constructor(container_name, data, showLegends=true) {
        this.dates = this.getUniqueDates(data["data"])
        this.root = this.transformData(data["data"])
        this.c_name = container_name
        this.margin = ({top: 30, right: 50, bottom: 30, left: 50})
        this.container = d3.select(container_name)
        this.width = this.container.node().getBoundingClientRect().width - this.margin.right;
        this.height = this.getHeight()
        this.container.style("height", (this.height + this.margin.bottom + this.margin.top) + "px");
        this.reference = data["reference"]
        this.showLegends = showLegends;
        this.buildSVG()
        this.tooltip = d3.select(this.c_name)
            .append("div")
            .style("opacity", 0)
            .attr("class", "tooltip")
            .style("position", "absolute")
            .style("background-color", "white")
            .style("border", "none")
            .style("padding", "5px")
            .style("width", "auto")
            .style("color", "black")
    }

    buildSVG() {
        let chart = this;
        let dates = this.getDates();
        dates.sort(function(a,b){return a.getTime() - b.getTime() > 0;});
        let y = d3.scaleLinear().range([this.height - this.margin.bottom, this.margin.top])
        let maximum = d3.max(this.root, (d,i,value) => d3.max(d.values, (el) => el.value))
        y.domain([0, maximum]).nice()
        let x = d3.scaleUtc().range([this.margin.left, this.width - this.margin.right])
        x.domain(d3.extent(dates))
        let z = d3.scaleOrdinal(d3.schemeCategory10).domain(this.root.map(d => d.key))
        let line = d3.line()
            .defined(d => !isNaN(d.value))
            .x(d => x(d.date_object))
            .y(d => y(d.value))

        let area = d3.area()
            .curve(d3.curveLinear)
            .x(d => x(d.date_object))
            .y0(y(0))
            .y1(d => y(d.value))

        const svg = this.container.append("svg")
            .attr("viewBox", [0, 0, this.width, this.height]);
        d3.selection.prototype.moveToFront = function() {
          return this.each(function(){
            this.parentNode.appendChild(this);
          });
        };
        d3.selection.prototype.moveToBack = function() {
            return this.each(function() {
                var firstChild = this.parentNode.firstChild;
                if (firstChild) {
                    this.parentNode.insertBefore(this, firstChild);
                }
            });
        };
        let reference = this.root.find(el => el.key == this.reference);
        let reference_name = this.reference;
        var filtered = this.root.filter(function(value, index, arr){ return value.key !== reference_name;});
        let path = svg.append("path")
            .datum(reference.values)
            .attr("fill", "steelblue")
            .attr("d", area)
            .attr("fill-opacity", 0.4);
        if(this.showLegends){
            this.addLegend(filtered, svg, z, reference);
        }
        let line_graph = svg.append("g")
            .attr("stroke-linejoin", "round")
            .attr("stroke-linecap", "round")
            .selectAll("path")
            .data(filtered)
            .join("path")
        line_graph
            .attr("d", d => line(d.values))
            .attr("stroke-width", 2)
            .attr("stroke", d => z(d.key))
            .attr("fill", "none")
            .attr('id', d => d.key);
        for(let i = 0; i < this.root.length; i++){
            svg.append('circle')
                .attr("id", 'circle_' + i.toString())
                .style("fill", "none")
                .attr("stroke", z(this.root[i].key))
                .attr('r', 8.5)
                .attr('cx', 0)
                .attr('cy', 0)
                .attr('opacity', 0)
        }


        svg.on('mousemove', function () {
                svg.selectAll('#vertical_limit').remove()
                svg.selectAll('#horizontal_limit').remove()
                const xm = x.invert(d3.mouse(this)[0]);
                let bisectDate = d3.bisector(function(d) { return d.getTime(); }).left;
                let indices = [];
                for(let index in chart.root){
                    let currentDates = getDateForCurrentValue([chart.root[index]])
                    currentDates.sort(function(a,b){return a.getTime() - b.getTime() > 0;});
                    indices.push(bisectDate(currentDates, xm.getTime(), 1));
                }

                const i1 = bisectDate(dates, xm.getTime(), 1);


                const i0 = i1 - 1;
                const i = xm - dates[i0] > dates[i1] - xm ? i1 : i0;

                //const i_value = chart.dates.indexOf(date)
                d3.select(this).attr('stroke-width', 3)
                svg.selectAll('#limit').remove()
                const pos_x = x(dates[i])

                svg.append('line')
                    .attr("id", 'vertical_limit')
                    .attr('x1', pos_x)
                    .attr('y1', chart.margin.top )
                    .attr('x2', pos_x)
                    .attr('y2', chart.height - chart.margin.top )
                    .attr('stroke', 'red')
                for(let i = 0; i < chart.root.length; i++){
                    let value = chart.root[i].values[indices[i]].value;
                    const pos_y = y(value);
                    svg.selectAll('#circle_' + i.toString())
                        .attr('cx', pos_x)
                        .attr('cy', pos_y)
                        .attr('opacity', 1)
                }

                d3.select(this).moveToFront();
                chart.tooltip
                    .html("<table><tr><td style='text-align: left;'><span style='color: black'>Date</span>: </td>" +
                        "<td style='text-align: right;'>" + chart.dates[indices[0]] + "</td></tr>" +
                            getHTMLForData(indices, chart.root, z, reference) + "</table>")
                    .style("top", (d3.event.pageY + 30) + "px")
                    .style("left", (d3.event.pageX + 30) + "px")
                    .style("opacity", 1)

            })
            .on('mouseleave', function (){
                d3.select(this).attr("stroke-width", 2)
                svg.selectAll('#vertical_limit').remove()
                d3.select(this).moveToBack()
                chart.tooltip
                .style("opacity", 0)
                });
        let xAxis = g => g
            .style("font", "14px sans-serif")
            .attr("transform", `translate(0,${this.height - this.margin.bottom})`)
            .call(d3.axisBottom(x).ticks(this.width / 80).tickSizeOuter(0))
        let yAxis = g => g
            .style("font", "14px sans-serif")
            .attr("transform", `translate(${this.margin.left},0)`)
            .call(d3.axisLeft(y).ticks(this.height / 80, "s").tickFormat(function(d){return d3.format(".2s")(d).replace(/G/, "B")}))
            .call(g => g.select(".domain").remove())
            .call(g => g.select(".domain").remove())
            .call(g => g.select(".tick:last-of-type text").clone()
                .attr("x", 3)
                .attr("text-anchor", "start")
                .attr("font-weight", "bold")
                .text("Amount"))
        svg.append("g")
            .call(xAxis);

        svg.append("g")
            .call(yAxis);
        var brush = d3.brushX().extent( [ [0,0], [chart.width,chart.height] ] )
        svg.append("g").attr("class", "brush").call(brush);
    }

    updateChart(){
        let extent = d3.event.selection
    }

    addLegend(filtered, svg, z, reference) {
        let size = 20
        for (let index in filtered) {
            let series = filtered[index]
            svg.append("line")
                .attr("x1", this.margin.right + size)
                .attr("y1", index * 10 * 3 / 2 + this.margin.top + size * 2)
                .attr("x2", this.margin.right + size + size * 3 / 2)
                .attr("y2", index * 10 * 3 / 2 + this.margin.top + size * 2)
                .attr("stroke", z(series.key))
                .attr("stroke-width", 3)
            svg.append("text")
                .attr("x", this.margin.right + size * 3)
                .attr("y", index * 10 * 3 / 2 + this.margin.top + size * 9 / 4)
                .attr("fill", "#fff")
                .attr("font-size", 15)
                .text(series.key)
        }
        svg.append("rect")
            .attr("x", this.margin.right + size)
            .attr("y", filtered.length * 10 * 3 / 2 + this.margin.top + size * 7 / 4)
            .attr("width", size * 3 / 2)
            .attr("height", size / 2)
            .attr("fill", "steelblue")
            .attr("fill-opacity", 0.4)
        svg.append("text")
            .attr("x", this.margin.right + size * 3)
            .attr("y", filtered.length * 10 * 3 / 2 + this.margin.top + size * 9 / 4)
            .attr("fill", "#fff")
            .attr("font-size", 15)
            .text(reference.key)
    }

    getDates(){
        return getDateForCurrentValue(this.root);
    }



    getUniqueDates(data){
        let dates= [];
        data.forEach((d) => {
            d.values.forEach((el) => {
                dates.push(el["date"])
            })
        });
        return Array.from(new Set(dates));
    }

    transformData(data) {
        let parseDate = d3.utcParse("%Y-%m-%d")
        data.forEach((d) => {
            d.values.forEach((el) => {
                const date = parseDate(el["date"]);
                el["date_object"] = date
            })
            d.values.sort(function(first, second) {
              return first.date_object.getTime() - second.date_object.getTime();
            });
        });
        return data;
    };

    getHeight() {
        return 500;
    }

}
function getDateForCurrentValue(value){
        let dates= [];
        value.forEach((d, i, value) => {
            d.values.forEach((el) => {
                dates.push(el["date_object"])
            })
        });
        return dates;
    }

Number.prototype.pad = function(size) {
  var s = String(this);
  while (s.length < (size || 2)) {s = "0" + s;}
  return s;
}

function getHTMLForData(indices, data, z, reference){
    let formatValue = x => isNaN(x) ? "N/A" : (Math.round(x * 100) / 100).toLocaleString("en")
    let html = ""
    for(let index in data){
        let series = data[index]
        const color = series.key === reference.key ? "steelblue": z(series.key)
        html += "<tr>"
        html += "<td style='text-align: left;'>"
        html += "<span style='color: " + color + "'>" + series.key.replace(/^\w/, c => c.toUpperCase()).replace("_", " ") + "</span>: "
        html += "</td>"
        html += "<td style='text-align: right;'>" + formatValue(series.values[indices[index]].value) + "</td>"
        html += "</tr>"
    }
    return html
}