class StackableBarChart extends BarChart {
    constructor(container_name, data, index_column) {
        super(container_name, data, ({top: 30, right: 30, bottom: 30, left: 30}));
        this.index_column = index_column
        this.x = d3.scaleBand()
            .domain(data.map(d => d.date))
            .range([this.margin.left, this.width - this.margin.right])
            .padding(0.1)
        this.y = d3.scaleLinear()
            .domain([0, d3.max(this.root, d => d3.max(d, d => d[1])) * 1.2])
            .rangeRound([this.height - this.margin.bottom, this.margin.top])
        this.color = d3.scaleOrdinal()
            .domain(this.root.map(d => d.key))
            .range(["#82b446", "#b44682"])
            .unknown("#ccc")
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
        let chart = this
        this.xAxis = g => g
            .attr("transform", `translate(0,${this.height - this.margin.bottom})`)
            .call(d3.axisBottom(this.x).tickValues(this.x.domain().filter(function (d, i) {
                return !(i % Math.ceil(chart.root[0].length / 6))
            })))
            .call(g => g.selectAll(".domain").remove());
        this.yAxis = g => g
            .attr("transform", `translate(${this.margin.left},0)`)
            .call(d3.axisLeft(this.y).ticks(5))
            .call(g => g.selectAll(".domain").remove())
            .call(g => g.append("line")
                .attr("stroke", "currentColor")
                .attr("y1", this.margin.top)
                .attr("y2", this.height - this.margin.bottom))
        this.buildSVG()
    }

    getHeight() {
        return 300;
    }

    transformData(data) {
        data.columns = Object.keys(data[0])
        array_move(data.columns, 1, 0)
        array_move(data.columns, 1, 2)
        data.forEach((d, i) => (d, d.total = d3.sum(Object.keys(d), c => d[c]), d))
        return d3.stack()
            .keys(data.columns.slice(1))
            (data)
            .map(d => (d.forEach(v => v.key = d.key), d));
    }

    buildSVG() {
        let chart = this
        const svg = this.container.append("svg")
            .attr("viewBox", [0, 0, this.width, this.height]);
        let formatValue = x => isNaN(x) ? "N/A" : (Math.round(x * 100) / 100).toLocaleString("en")

        // Three function that change the tooltip when user hover / move / leave a cell
        let mouseover = function (d) {
            chart.tooltip.style("opacity", 1)
        }
        let mousemove = function (d) {
            chart.tooltip
                .html("<table><tr><td style='text-align: left;'><span style='color: dodgerblue'>Date</span>: </td>" +
                    "<td style='text-align: right;'>" + d.data.date + "</td></tr>" +
                    "<tr><td style='text-align: left;'><span style='color: dodgerblue'>" +
                    d.key.replace(/^\w/, c => c.toUpperCase()).replace("_", " ") + "</span>: </td>" +
                    "<td style='text-align: right;'>" + formatValue(d.data[d.key]) + "</td></tr>" +
                    "</table>")
                .style("top", (d3.event.pageY + 30) + "px")
                .style("left", (d3.event.pageX + 30) + "px")
        }
        let mouseleave = function (d) {
            chart.tooltip
                .style("opacity", 0)
        }

        let bar = svg.append("g")
            .selectAll("g")
            .data(this.root)
            .join("g")
        bar.attr("fill", d => this.color(d.key))
            .selectAll("rect")
            .data(d => d)
            .join("rect")
            .attr("x", (d, i) => this.x(d.data.date))
            .attr("y", d => this.y(d[1]))
            .attr("height", d => this.y(d[0]) - this.y(d[1]))
            .attr("width", this.x.bandwidth())
            .on('mouseenter', function (actual, i) {
                d3.select(this).attr('opacity', 0.5)
                bar.selectAll('#limit').remove()
                const pos_y = chart.y(actual[1])
                bar.append('line')
                    .attr('id', 'limit')
                    .attr('x1', chart.margin.left)
                    .attr('y1', pos_y)
                    .attr('x2', chart.width - chart.margin.right - chart.margin.left)
                    .attr('y2', pos_y)
                    .attr('stroke', 'red')
            })
            .on('mouseover', mouseover)
            .on('mouseleave', function (actual, i) {
                d3.select(this).attr('opacity', 1)
                bar.selectAll('#limit').remove()
                mouseleave(actual);
            })
            .on('mousemove', mousemove);

        svg.append("g")
            .call(this.xAxis);

        svg.append("g")
            .call(this.yAxis);

    }

}

function array_move(arr, old_index, new_index) {
    if (new_index >= arr.length) {
        var k = new_index - arr.length + 1;
        while (k--) {
            arr.push(undefined);
        }
    }
    arr.splice(new_index, 0, arr.splice(old_index, 1)[0]);
};